#!/usr/bin/env python3
"""
Surf CLI Web Verification Helper

Runs Surf CLI verification workflow and produces artifacts that the stop hook
validates. This is NOT a hook itself - it's a helper script called by appfix.

Usage:
    python3 surf-verify.py --urls "https://example.com" "https://example.com/dashboard"
    python3 surf-verify.py --from-topology  # Read URLs from service-topology.md

Artifacts produced in .claude/web-smoke/:
    - summary.json          Pass/fail + metadata
    - screenshots/          Page screenshots
    - console.txt           Browser console output
    - failing-requests.sh   Curl repros for failed requests

Exit codes:
    0 - Verification passed
    1 - Verification failed (errors found)
    2 - Setup error (Surf not installed, missing URLs, etc.)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ARTIFACT_DIR = ".claude/web-smoke"
WAIVERS_PATH = f"{ARTIFACT_DIR}/waivers.json"


def get_git_version() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def load_waivers() -> dict:
    """Load waiver patterns if they exist."""
    if not os.path.exists(WAIVERS_PATH):
        return {"console_patterns": [], "network_patterns": []}
    try:
        with open(WAIVERS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"console_patterns": [], "network_patterns": []}


def matches_waiver(text: str, patterns: list[str]) -> bool:
    """Check if text matches any waiver pattern."""
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def check_surf_installed() -> bool:
    """Check if Surf CLI is installed."""
    try:
        result = subprocess.run(
            ["which", "surf"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def read_urls_from_topology() -> list[str]:
    """Read URLs from service-topology.md if it exists."""
    topology_paths = [
        ".claude/skills/appfix/references/service-topology.md",
        Path.home() / ".claude" / "skills" / "appfix" / "references" / "service-topology.md",
    ]

    for path in topology_paths:
        path = Path(path)
        if not path.exists():
            continue

        content = path.read_text()
        # Look for web_smoke_urls section
        match = re.search(r"web_smoke_urls:\s*\n((?:\s*-\s*https?://[^\n]+\n?)+)", content)
        if match:
            urls_block = match.group(1)
            urls = re.findall(r"-\s*(https?://[^\s]+)", urls_block)
            return urls

    return []


def run_surf_workflow(urls: list[str]) -> dict:
    """Run Surf workflow and collect artifacts."""
    os.makedirs(f"{ARTIFACT_DIR}/screenshots", exist_ok=True)

    waivers = load_waivers()
    results = {
        "passed": True,
        "tested_at": datetime.utcnow().isoformat() + "Z",
        "tested_at_version": get_git_version(),
        "urls_tested": urls,
        "screenshot_count": 0,
        "console_errors": 0,
        "network_errors": 0,
        "failing_requests": [],
        "waivers_applied": 0,
    }

    all_console_output = []
    all_failing_requests = []

    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] Testing: {url}")

        # Navigate to URL (tab.new creates tab AND navigates)
        try:
            nav_result = subprocess.run(
                ["surf", "tab.new", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if nav_result.returncode != 0:
                print(f"  ✗ Navigation failed: {nav_result.stderr}")
                results["network_errors"] += 1
                results["passed"] = False
                continue
        except subprocess.TimeoutExpired:
            print("  ✗ Navigation timeout")
            results["network_errors"] += 1
            results["passed"] = False
            continue
        except FileNotFoundError:
            print("ERROR: surf command not found. Install with: npm install -g @nicobailon/surf-cli")
            sys.exit(2)

        # Take screenshot
        screenshot_path = f"{ARTIFACT_DIR}/screenshots/page_{i}.png"
        try:
            subprocess.run(
                ["surf", "screenshot", "--output", screenshot_path],
                capture_output=True,
                timeout=10,
            )
            if os.path.exists(screenshot_path):
                results["screenshot_count"] += 1
                print(f"  ✓ Screenshot saved: {screenshot_path}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠ Screenshot failed")

        # Capture console output
        try:
            console = subprocess.run(
                ["surf", "console"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            console_output = console.stdout

            # Count errors (filter by waivers)
            for line in console_output.split("\n"):
                if "error" in line.lower():
                    if matches_waiver(line, waivers.get("console_patterns", [])):
                        results["waivers_applied"] += 1
                    else:
                        results["console_errors"] += 1
                        all_console_output.append(f"[ERROR] {url}: {line}")

            all_console_output.append(f"=== {url} ===\n{console_output}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("  ⚠ Console capture failed")

        # Capture network errors (4xx/5xx)
        try:
            network = subprocess.run(
                ["surf", "network", "--status", "4xx,5xx", "--format", "curl"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if network.stdout.strip():
                for line in network.stdout.strip().split("\n"):
                    if line.strip():
                        if matches_waiver(line, waivers.get("network_patterns", [])):
                            results["waivers_applied"] += 1
                        else:
                            results["network_errors"] += 1
                            all_failing_requests.append(line)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Write console output
    with open(f"{ARTIFACT_DIR}/console.txt", "w") as f:
        f.write("\n".join(all_console_output))

    # Write failing requests as curl commands
    if all_failing_requests:
        with open(f"{ARTIFACT_DIR}/failing-requests.sh", "w") as f:
            f.write("#!/bin/bash\n# Curl commands to reproduce failing requests\n\n")
            f.write("\n".join(all_failing_requests))
        results["failing_requests"] = all_failing_requests

    # Determine pass/fail
    if results["console_errors"] > 0 or results["network_errors"] > 0:
        results["passed"] = False

    if results["screenshot_count"] == 0:
        results["passed"] = False

    # Write summary
    with open(f"{ARTIFACT_DIR}/summary.json", "w") as f:
        json.dump(results, f, indent=2)

    return results


def print_summary(results: dict) -> None:
    """Print human-readable summary."""
    status = "PASSED" if results["passed"] else "FAILED"
    status_emoji = "✓" if results["passed"] else "✗"

    print(f"\n{'='*60}")
    print(f"  {status_emoji} Web Smoke Verification: {status}")
    print(f"{'='*60}")
    print(f"  URLs tested:       {len(results['urls_tested'])}")
    print(f"  Screenshots:       {results['screenshot_count']}")
    print(f"  Console errors:    {results['console_errors']}")
    print(f"  Network errors:    {results['network_errors']}")
    print(f"  Waivers applied:   {results['waivers_applied']}")
    print(f"  Version:           {results['tested_at_version']}")
    print(f"  Artifacts:         {ARTIFACT_DIR}/")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Run Surf CLI web verification")
    parser.add_argument(
        "--urls",
        nargs="+",
        help="URLs to test",
    )
    parser.add_argument(
        "--from-topology",
        action="store_true",
        help="Read URLs from service-topology.md",
    )
    args = parser.parse_args()

    # Check Surf is installed
    if not check_surf_installed():
        print("ERROR: Surf CLI is not installed.")
        print("Install with: npm install -g @nicobailon/surf-cli")
        print("\nAlternatively, use Chrome MCP for manual verification.")
        sys.exit(2)

    # Get URLs
    urls = []
    if args.from_topology:
        urls = read_urls_from_topology()
        if not urls:
            print("ERROR: No web_smoke_urls found in service-topology.md")
            print("Add URLs to service-topology.md under web_smoke_urls:")
            print("  web_smoke_urls:")
            print("    - https://staging.example.com/")
            print("    - https://staging.example.com/dashboard")
            sys.exit(2)
    elif args.urls:
        urls = args.urls
    else:
        print("ERROR: No URLs specified. Use --urls or --from-topology")
        sys.exit(2)

    print("Starting web smoke verification...")
    print(f"URLs to test: {urls}\n")

    # Run verification
    results = run_surf_workflow(urls)
    print_summary(results)

    # Exit with appropriate code
    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
