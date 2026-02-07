#!/usr/bin/env python3
"""
Memory Writer CLI

Standalone CLI wrapper for auto_capture_memory. Enables agent-type hooks
to trigger memory capture independently of the stop-validator flow.

Usage:
    memory-writer.py --cwd /path/to/project [--checkpoint /path/to/checkpoint.json]
    memory-writer.py --cwd /path/to/project --stdin < checkpoint.json

Exit codes:
    0 - Success
    1 - Error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import log_debug, timed_hook
from _session import load_checkpoint


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Capture memory event from checkpoint data"
    )
    parser.add_argument(
        "--cwd",
        required=True,
        help="Working directory (project root)",
    )
    parser.add_argument(
        "--checkpoint",
        help="Path to checkpoint JSON file (optional if --stdin used)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read checkpoint JSON from stdin",
    )

    args = parser.parse_args()

    # Load checkpoint from stdin or file
    checkpoint = None

    if args.stdin:
        try:
            checkpoint = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            result = {
                "captured": False,
                "error": f"Invalid JSON from stdin: {e}"
            }
            print(json.dumps(result))
            log_debug(
                f"Failed to parse stdin: {e}",
                hook_name="memory-writer",
            )
            return 1
    elif args.checkpoint:
        try:
            checkpoint_path = Path(args.checkpoint)
            if not checkpoint_path.exists():
                result = {
                    "captured": False,
                    "error": f"Checkpoint file not found: {args.checkpoint}"
                }
                print(json.dumps(result))
                return 1
            checkpoint = json.loads(checkpoint_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            result = {
                "captured": False,
                "error": f"Failed to read checkpoint: {e}"
            }
            print(json.dumps(result))
            log_debug(
                f"Failed to read checkpoint file: {e}",
                hook_name="memory-writer",
            )
            return 1
    else:
        # No checkpoint source specified, try loading from default location
        checkpoint = load_checkpoint(args.cwd)
        if checkpoint is None:
            result = {
                "captured": False,
                "error": "No checkpoint found at .claude/completion-checkpoint.json"
            }
            print(json.dumps(result))
            return 1

    # Import and call auto_capture_memory
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "stop_validator",
            Path(__file__).parent / "stop-validator.py"
        )
        if spec and spec.loader:
            stop_validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(stop_validator)
            auto_capture_memory = stop_validator.auto_capture_memory
        else:
            raise ImportError("Could not load stop-validator.py")
    except (ImportError, AttributeError) as e:
        result = {
            "captured": False,
            "error": f"Failed to import auto_capture_memory: {e}"
        }
        print(json.dumps(result))
        log_debug(
            f"Import failed: {e}",
            hook_name="memory-writer",
        )
        return 1

    # Trigger memory capture
    try:
        auto_capture_memory(args.cwd, checkpoint)
        result = {"captured": True}
        print(json.dumps(result))
        log_debug(
            "Memory capture successful",
            hook_name="memory-writer",
            parsed_data={"cwd": args.cwd},
        )
        return 0
    except Exception as e:
        result = {
            "captured": False,
            "error": f"Memory capture failed: {e}"
        }
        print(json.dumps(result))
        log_debug(
            f"Capture failed: {e}",
            hook_name="memory-writer",
            error=e,
        )
        return 1


if __name__ == "__main__":
    with timed_hook("memory-writer"):
        sys.exit(main())
