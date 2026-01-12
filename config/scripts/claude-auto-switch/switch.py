#!/usr/bin/env python3
"""
Claude Auto-Switch: Automatic account failover on rate limit.

Monitors Claude Code output for rate limit messages and automatically
switches to a backup account, preserving conversation context.

Usage:
    python switch.py [claude args...]

Or via alias:
    alias claude="python3 ~/.claude/scripts/claude-auto-switch/switch.py"

Configuration:
    Edit config.json in the same directory to configure accounts and patterns.
"""
import json
import os
import pty
import re
import select
import signal
import sys
import termios
import tty
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
CONTEXT_FILE = Path.home() / ".claude" / ".auto-switch-context.md"
SESSION_FILE = Path.home() / ".claude" / ".auto-switch-session"

# UUID pattern for session ID detection
SESSION_ID_PATTERN = re.compile(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", re.IGNORECASE)


def load_config() -> dict:
    """Load account configuration."""
    if not CONFIG_FILE.exists():
        print(f"❌ Config file not found: {CONFIG_FILE}")
        print("   Run install.sh or create config.json manually.")
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        return json.load(f)


def expand_path(p: str) -> Path:
    """Expand ~ and env vars in path."""
    return Path(os.path.expanduser(os.path.expandvars(p)))


def detect_rate_limit(line: str, patterns: list[str]) -> bool:
    """Check if output indicates rate limit."""
    line_lower = line.lower()
    return any(re.search(p, line_lower) for p in patterns)


def save_context(conversation_summary: str):
    """Save conversation context for next account."""
    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(f"""# Auto-Switch Context
Saved: {datetime.now().isoformat()}

## Previous Conversation Summary
{conversation_summary}

---
*This context was auto-saved when switching accounts due to rate limit.*
""")
    print(f"💾 Context saved to {CONTEXT_FILE}")


def load_context() -> str | None:
    """Load saved context if exists."""
    if CONTEXT_FILE.exists():
        content = CONTEXT_FILE.read_text()
        CONTEXT_FILE.unlink()  # One-time use
        return content
    return None


def save_session_id(session_id: str):
    """Save session ID for resume on next account."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(session_id)
    print(f"📎 Session ID saved: {session_id[:8]}...")


def load_session_id() -> str | None:
    """Load saved session ID if exists."""
    if SESSION_FILE.exists():
        session_id = SESSION_FILE.read_text().strip()
        SESSION_FILE.unlink()  # One-time use
        return session_id if session_id else None
    return None


def extract_session_id(line: str) -> str | None:
    """Extract session ID from output line."""
    match = SESSION_ID_PATTERN.search(line)
    return match.group(1) if match else None


def capture_conversation_buffer(output_lines: list[str], max_lines: int = 100) -> str:
    """Extract recent conversation for context preservation."""
    # Get last N lines, filter out system noise
    relevant = []
    for line in output_lines[-max_lines:]:
        stripped = line.strip()
        # Skip UI chrome and empty lines
        if not stripped:
            continue
        if stripped.startswith("─") or stripped.startswith("╭") or stripped.startswith("╰"):
            continue
        if stripped.startswith("│") and len(stripped) < 5:
            continue
        relevant.append(line)

    return "\n".join(relevant[-50:])  # Keep last 50 relevant lines


def run_claude_interactive(
    account: dict,
    args: list[str],
    patterns: list[str],
    session_id_to_resume: str | None = None,
) -> tuple[int, list[str], str | None]:
    """
    Run claude interactively with PTY for proper terminal handling.
    Returns (exit_code, output_lines, captured_session_id).
    exit_code -1 means rate limit detected.
    """
    config_dir = expand_path(account["config_dir"])
    default_config_dir = Path.home() / ".claude"

    if not config_dir.exists():
        print(f"\n⚠️  Config directory not found: {config_dir}")
        print(f"   First, authenticate this account:")
        print(f"   CLAUDE_CONFIG_DIR={config_dir} claude")
        print()
        return 1, [], None

    env = os.environ.copy()

    # Only set CLAUDE_CONFIG_DIR for non-default directories
    # Setting it explicitly (even to ~/.claude) can break MCP server detection
    if config_dir != default_config_dir:
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)

    print(f"\n🔄 Using account: {account['name']} ({config_dir.name})")

    # Build command
    cmd = ["claude"] + args

    # If resuming a session, use --resume flag
    if session_id_to_resume:
        print(f"📋 Resuming session: {session_id_to_resume[:8]}...")
        cmd.extend(["--resume", session_id_to_resume])

    output_lines: list[str] = []
    rate_limit_detected = False
    captured_session_id: str | None = None

    # Save original terminal settings
    stdin_fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin_fd)

    # Use PTY for interactive terminal handling
    pid, fd = pty.fork()

    if pid == 0:
        # Child process
        os.execvpe(cmd[0], cmd, env)
    else:
        # Parent process
        try:
            # Set terminal to raw mode for proper keystroke handling
            tty.setraw(stdin_fd)

            while True:
                # Monitor BOTH stdin AND PTY for data
                ready, _, _ = select.select([fd, stdin_fd], [], [], 0.1)

                # Forward stdin to PTY (user input)
                if stdin_fd in ready:
                    try:
                        data = os.read(stdin_fd, 4096)
                        if data:
                            os.write(fd, data)
                    except OSError:
                        pass

                # Read PTY output and display
                if fd in ready:
                    try:
                        data = os.read(fd, 4096)
                        if not data:
                            break
                        text = data.decode("utf-8", errors="replace")
                        sys.stdout.write(text)
                        sys.stdout.flush()

                        # Track output for context preservation and session ID capture
                        for line in text.splitlines():
                            output_lines.append(line)

                            # Capture session ID from early output (first 50 lines)
                            if captured_session_id is None and len(output_lines) < 50:
                                session_id = extract_session_id(line)
                                if session_id:
                                    captured_session_id = session_id

                            if detect_rate_limit(line, patterns):
                                rate_limit_detected = True
                                # Restore terminal before printing
                                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
                                print(
                                    f"\n\n⚠️  Rate limit detected on account: {account['name']}"
                                )
                                # Send interrupt to child
                                os.kill(pid, signal.SIGTERM)
                                break

                        if rate_limit_detected:
                            break

                    except OSError:
                        break

                # Check if child has exited
                result = os.waitpid(pid, os.WNOHANG)
                if result[0] != 0:
                    break

        except KeyboardInterrupt:
            os.kill(pid, signal.SIGTERM)
            raise
        finally:
            # Always restore terminal settings
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            try:
                os.close(fd)
            except OSError:
                pass

        # Wait for child to exit with timeout, then force kill if needed
        import time

        exit_code = 0
        for _ in range(30):  # 3 second timeout (30 * 0.1s)
            result = os.waitpid(pid, os.WNOHANG)
            if result[0] != 0:
                exit_code = os.WEXITSTATUS(result[1]) if os.WIFEXITED(result[1]) else 1
                break
            time.sleep(0.1)
        else:
            # Child didn't respond to SIGTERM, force kill
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
            exit_code = 1

        if rate_limit_detected:
            return -1, output_lines, captured_session_id

        return exit_code, output_lines, captured_session_id


def main():
    # Parse our own arguments (before --)
    args = sys.argv[1:]

    # Load configuration
    config = load_config()
    accounts = config["accounts"]
    patterns = config["detection_patterns"]

    if not accounts:
        print("❌ No accounts configured in config.json")
        return 1

    # Check for saved session ID from previous switch
    saved_session_id = load_session_id()
    if saved_session_id:
        print(f"📋 Found session to resume: {saved_session_id[:8]}...")

    current_idx = 0
    all_output: list[str] = []
    current_session_id: str | None = saved_session_id

    while current_idx < len(accounts):
        account = accounts[current_idx]

        # Resume session on switch (not first run, or if saved session exists)
        resume_id = None
        if current_idx > 0 and current_session_id:
            resume_id = current_session_id
        elif saved_session_id and current_idx == 0:
            # Don't auto-resume on first run - let user control that
            saved_session_id = None

        exit_code, output, captured_id = run_claude_interactive(account, args, patterns, resume_id)
        all_output.extend(output)

        # Update session ID if captured
        if captured_id:
            current_session_id = captured_id

        if exit_code == -1:  # Rate limit
            # Save session ID for next account
            if current_session_id:
                save_session_id(current_session_id)

            current_idx += 1
            if current_idx < len(accounts):
                next_account = accounts[current_idx]
                print(f"\n🔄 Switching to: {next_account['name']}...")
                print("   Press Ctrl+C to abort switch\n")
                try:
                    import time

                    time.sleep(2)  # Give user chance to abort
                except KeyboardInterrupt:
                    print("\n❌ Switch aborted by user")
                    return 1
            else:
                print("\n❌ All accounts have hit rate limits!")
                print("   Wait for limits to reset or add more accounts to config.json")
                return 1
            continue

        return exit_code

    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(130)
