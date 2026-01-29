#!/usr/bin/env python3
"""
Claude Code hook that emits structured events to Mimesis gateway.

Reads hook JSON from stdin, enriches with FLEET_SESSION_ID, writes to Unix socket.
For Stop hooks, also reads JSONL transcript to extract assistant response text and thinking.

This enables structured event delivery for PTY sessions, which would otherwise
only receive raw stdout chunks with ANSI escape codes.

Hook types supported:
- PreToolUse: Emits tool event with phase="pre"
- PostToolUse: Emits tool event with phase="post"
- Stop: Reads transcript to emit text/thinking events
- Notification: Emits as status_change event
"""
import json
import os
import socket
import sys
from pathlib import Path

# Mimesis gateway Unix socket path
FLEET_SOCKET = os.path.expanduser("~/.fleet/gateway.sock")


def emit_event(event: dict) -> bool:
    """Send event to Mimesis gateway via Unix socket.

    Returns True if successful, False otherwise.
    """
    socket_path = Path(FLEET_SOCKET)
    if not socket_path.exists():
        # Socket doesn't exist - daemon not running, silently skip
        return False

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)  # 1 second timeout
        sock.connect(str(socket_path))
        sock.sendall((json.dumps(event) + "\n").encode())
        sock.close()
        return True
    except Exception as e:
        # Log to stderr for debugging (won't affect hook behavior)
        print(f"[gateway-emit] Failed to emit: {e}", file=sys.stderr)
        return False


def read_last_assistant_entry(transcript_path: str) -> dict | None:
    """Read the last assistant entry from a JSONL transcript.

    Claude Code maintains a JSONL transcript of the conversation.
    Each line is a JSON object with "role" (assistant/user/system) and "content".
    """
    if not transcript_path:
        return None

    path = Path(transcript_path)
    if not path.exists():
        return None

    last_assistant = None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("role") == "assistant":
                        last_assistant = entry
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return last_assistant


def main():
    # Read hook JSON from stdin
    try:
        hook_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Invalid JSON from stdin - exit silently
        return

    # Get session ID from environment or hook data
    # FLEET_SESSION_ID is set by Mimesis when spawning PTY sessions
    session_id = os.environ.get("FLEET_SESSION_ID", "")
    if not session_id:
        session_id = hook_data.get("session_id", "")

    if not session_id:
        # No session ID - can't emit events, exit silently
        return

    # Get hook name from environment (set by Claude Code)
    hook_name = os.environ.get("CLAUDE_HOOK_NAME", "unknown")

    # Build base event with required fields
    event = {
        "fleet_session_id": session_id,
        "hook_type": hook_name,
        "timestamp": hook_data.get("timestamp") or None,
        "cwd": hook_data.get("cwd"),
    }

    # Handle tool events (PreToolUse, PostToolUse)
    if hook_name in ("PreToolUse", "PostToolUse"):
        event["tool_name"] = hook_data.get("tool_name")
        event["tool_input"] = hook_data.get("tool_input")
        event["tool_result"] = hook_data.get("tool_result")
        event["phase"] = "pre" if hook_name == "PreToolUse" else "post"
        event["ok"] = hook_data.get("ok", True)
        emit_event(event)

    # Handle Stop hook - extract text/thinking from JSONL transcript
    elif hook_name == "Stop":
        transcript_path = hook_data.get("transcript_path")
        assistant_entry = read_last_assistant_entry(transcript_path)

        if assistant_entry and "content" in assistant_entry:
            for block in assistant_entry.get("content", []):
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type")

                # Text content block
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        text_event = {
                            **event,
                            "event_type": "text",
                            "text": text,
                        }
                        emit_event(text_event)

                # Thinking content block (extended thinking)
                elif block_type == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking:
                        thinking_event = {
                            **event,
                            "event_type": "thinking",
                            "thinking": thinking,
                        }
                        emit_event(thinking_event)

    # Handle Notification hook - emit as status change
    elif hook_name == "Notification":
        message = hook_data.get("message", "")
        event["event_type"] = "status_change"
        event["from"] = "working"
        event["to"] = message[:50] if message else "notification"
        emit_event(event)


if __name__ == "__main__":
    main()
