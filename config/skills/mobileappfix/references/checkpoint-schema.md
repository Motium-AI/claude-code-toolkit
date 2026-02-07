# Completion Checkpoint Schema (Mobile)

The checkpoint file `.claude/completion-checkpoint.json` tracks task completion for the stop hook validator.

## Schema

```json
{
  "self_report": {
    "code_changes_made": true,
    "maestro_tests_passed": true,
    "maestro_tests_passed_at_version": "abc1234",
    "unit_tests_passed": true,
    "unit_tests_passed_at_version": "abc1234",
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "is_job_complete": true
  },
  "validation_tests": {
    "tests": [
      {
        "id": "login_flow",
        "description": "User can log in and see stepping stones",
        "type": "maestro_flow",
        "expected": "J2-returning-user-login passes",
        "actual": "PASSED - all assertions passed",
        "passed": true
      }
    ],
    "summary": {
      "total": 1,
      "passed": 1,
      "failed": 0,
      "last_run_version": "abc1234"
    }
  },
  "reflection": {
    "what_was_done": "Fixed navigation guard timing issue, login flow now works correctly",
    "what_remains": "none",
    "blockers": null
  },
  "evidence": {
    "maestro_flows_tested": [
      "J2-returning-user-login.yaml"
    ],
    "screenshots": [
      ".claude/maestro-smoke/j2_07_stepping_stones_visible.png"
    ],
    "platform": "ios",
    "device": "iPhone 15 Pro Simulator"
  }
}
```

## Field Reference

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `code_changes_made` | bool | yes | Were any code files modified? |
| `maestro_tests_passed` | bool | yes | Did Maestro E2E tests pass? |
| `maestro_tests_passed_at_version` | string | yes | Git version when Maestro passed |
| `unit_tests_passed` | bool | conditional | Did Jest tests pass? |
| `linters_pass` | bool | if code changed | Did lint + typecheck pass? |
| `is_job_complete` | bool | yes | **Critical** - Is the job ACTUALLY done? |
| `what_remains` | string | yes | Must be "none" to allow stop |

## Version Tracking

Version-dependent fields (`*_at_version`) become **stale** when code changes after verification:

```
maestro_tests_passed_at_version: abc1234
current_version:                 def5678  <- Different!
-> STALE: Must re-verify
```

When code changes after verification, you must re-verify before stopping. The stop-validator checks version consistency.

## Pass Conditions

The stop hook requires ALL of these to stop:

1. `is_job_complete: true`
2. `what_remains` is empty or "none"
3. If code changed: `linters_pass: true` with current version
4. `maestro_tests_passed: true` with current version (for mobile)
