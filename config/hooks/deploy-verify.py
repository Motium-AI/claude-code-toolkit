#!/usr/bin/env python3
"""
GitHub Actions Deployment Verification Helper

Runs gh CLI commands to verify deployment status and produces artifacts that
the stop hook validates. This is NOT a hook itself - it's a helper script
called by appfix/godo workflows.

Usage:
    python3 deploy-verify.py --workflow deploy.yml
    python3 deploy-verify.py --workflow deploy.yml --environment staging
    python3 deploy-verify.py --from-topology  # Read from service-topology.md

Artifacts produced in .claude/deployment/:
    - summary.json          Pass/fail + metadata
    - workflow-log.txt      gh run log output

Exit codes:
    0 - Verification passed
    1 - Verification failed (deployment failed or version mismatch)
    2 - Setup error (gh not installed, missing args, etc.)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARTIFACT_DIR = ".claude/deployment"


def get_git_version() -> str:
    """Get current git commit hash (short)."""
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


def get_git_full_sha() -> str:
    """Get current git commit full SHA for comparison with gh output."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def check_gh_installed() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def read_workflow_from_topology() -> dict:
    """Read deployment workflow config from service-topology.md if it exists."""
    topology_paths = [
        ".claude/skills/appfix/references/service-topology.md",
        Path.home()
        / ".claude"
        / "skills"
        / "appfix"
        / "references"
        / "service-topology.md",
    ]

    for path in topology_paths:
        path = Path(path)
        if not path.exists():
            continue

        content = path.read_text()
        # Look for deploy_workflow section
        workflow_match = re.search(r"deploy_workflow:\s*(\S+)", content)
        env_match = re.search(r"deploy_environment:\s*(\S+)", content)

        config = {}
        if workflow_match:
            config["workflow"] = workflow_match.group(1)
        if env_match:
            config["environment"] = env_match.group(1)
        if config:
            return config

    return {}


def get_latest_run(workflow: str) -> dict | None:
    """Get the latest workflow run via gh CLI."""
    try:
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow,
                "--limit",
                "1",
                "--json",
                "databaseId,status,conclusion,headSha,createdAt,url",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"  gh run list failed: {result.stderr.strip()}")
            return None

        runs = json.loads(result.stdout)
        if not runs:
            return None
        return runs[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  Error querying workflow runs: {e}")
        return None


def get_run_log(run_id: int) -> str:
    """Get workflow run log output."""
    try:
        result = subprocess.run(
            ["gh", "run", "view", str(run_id), "--log"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout if result.returncode == 0 else result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "Failed to retrieve run log"


def verify_deployment(workflow: str, environment: str | None = None) -> dict:
    """Verify deployment status and collect artifacts."""
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    current_short = get_git_version()
    current_full = get_git_full_sha()

    results = {
        "passed": False,
        "deployed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "deployed_version": "",
        "tested_at_version": current_short,
        "workflow_name": workflow,
        "environment": environment or "default",
        "run_id": None,
        "run_url": "",
        "conclusion": "",
        "status": "",
        "version_match": False,
        "errors": [],
    }

    # Get latest run
    print(f"Checking latest run for workflow: {workflow}")
    run = get_latest_run(workflow)

    if not run:
        results["errors"].append(
            f"No runs found for workflow '{workflow}'. "
            "Has the workflow been triggered? Run: gh workflow run {workflow}"
        )
        return results

    run_id = run.get("databaseId")
    status = run.get("status", "")
    conclusion = run.get("conclusion", "")
    head_sha = run.get("headSha", "")
    run_url = run.get("url", "")

    results["run_id"] = run_id
    results["run_url"] = run_url
    results["status"] = status
    results["conclusion"] = conclusion
    results["deployed_version"] = head_sha[:7] if head_sha else ""

    print(f"  Run ID: {run_id}")
    print(f"  Status: {status}")
    print(f"  Conclusion: {conclusion}")
    print(f"  Head SHA: {head_sha[:7] if head_sha else 'unknown'}")
    print(f"  URL: {run_url}")

    # Check if run is still in progress
    if status != "completed":
        results["errors"].append(
            f"Workflow run {run_id} is still '{status}'. "
            "Wait for completion: gh run watch {run_id} --exit-status"
        )
        return results

    # Check conclusion
    if conclusion != "success":
        results["errors"].append(
            f"Workflow run {run_id} concluded with '{conclusion}' (expected 'success'). "
            f"Check logs: gh run view {run_id} --log"
        )
        # Save log for diagnosis
        log = get_run_log(run_id)
        log_path = Path(ARTIFACT_DIR) / "workflow-log.txt"
        log_path.write_text(log)
        print(f"  Workflow log saved to: {log_path}")
        return results

    # Check version match
    if head_sha and current_full != "unknown":
        if current_full.startswith(head_sha) or head_sha.startswith(current_full):
            results["version_match"] = True
            print(f"  Version match: current={current_short}, deployed={head_sha[:7]}")
        else:
            results["version_match"] = False
            results["errors"].append(
                f"Version MISMATCH: deployed SHA '{head_sha[:7]}' != "
                f"current HEAD '{current_short}'. "
                "Code changed after deployment. Re-deploy required."
            )
            print(
                f"  Version MISMATCH: deployed={head_sha[:7]}, current={current_short}"
            )
            return results
    elif not head_sha:
        results["errors"].append("Cannot determine deployed SHA from workflow run")
        return results

    # All checks passed
    results["passed"] = True

    # Save log
    log = get_run_log(run_id)
    log_path = Path(ARTIFACT_DIR) / "workflow-log.txt"
    log_path.write_text(log)

    return results


def print_summary(results: dict) -> None:
    """Print human-readable summary."""
    status = "PASSED" if results["passed"] else "FAILED"
    status_char = "+" if results["passed"] else "x"

    print(f"\n{'=' * 60}")
    print(f"  [{status_char}] Deployment Verification: {status}")
    print(f"{'=' * 60}")
    print(f"  Workflow:          {results['workflow_name']}")
    print(f"  Environment:       {results['environment']}")
    print(f"  Run ID:            {results.get('run_id', 'N/A')}")
    print(f"  Conclusion:        {results.get('conclusion', 'N/A')}")
    print(f"  Version match:     {results.get('version_match', False)}")
    print(f"  Deployed version:  {results.get('deployed_version', 'N/A')}")
    print(f"  Current version:   {results.get('tested_at_version', 'N/A')}")
    print(f"  Artifacts:         {ARTIFACT_DIR}/")

    if results.get("errors"):
        print("\n  Errors:")
        for err in results["errors"]:
            print(f"    - {err}")

    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Verify GitHub Actions deployment")
    parser.add_argument(
        "--workflow",
        help="Workflow file name (e.g., deploy.yml)",
    )
    parser.add_argument(
        "--environment",
        help="Deployment environment (e.g., staging, production)",
    )
    parser.add_argument(
        "--from-topology",
        action="store_true",
        help="Read workflow config from service-topology.md",
    )
    args = parser.parse_args()

    # Check gh is installed
    if not check_gh_installed():
        print("ERROR: gh CLI is not installed or not authenticated.")
        print("Install: https://cli.github.com/")
        print("Auth: gh auth login")
        sys.exit(2)

    # Get workflow config
    workflow = args.workflow
    environment = args.environment

    if args.from_topology:
        config = read_workflow_from_topology()
        if not config.get("workflow"):
            print("ERROR: No deploy_workflow found in service-topology.md")
            print("Add to service-topology.md:")
            print("  deploy_workflow: deploy.yml")
            print("  deploy_environment: staging")
            sys.exit(2)
        workflow = config["workflow"]
        environment = environment or config.get("environment")

    if not workflow:
        print("ERROR: No workflow specified. Use --workflow or --from-topology")
        sys.exit(2)

    print("Starting deployment verification...")
    print(f"Workflow: {workflow}")
    if environment:
        print(f"Environment: {environment}")
    print()

    # Run verification
    results = verify_deployment(workflow, environment)

    # Write summary
    summary_path = Path(ARTIFACT_DIR) / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2))

    print_summary(results)

    # Exit with appropriate code
    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
