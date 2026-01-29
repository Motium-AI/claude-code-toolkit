# Completion Checkpoint Schema

## Full Field Reference

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `code_changes_made` | bool | yes | Were any code files modified? |
| `web_testing_done` | bool | yes | Did you verify in a real browser? |
| `web_testing_done_at_version` | string | if tested | Git version when tested |
| `deployed` | bool | conditional | Did you deploy the changes? |
| `deployed_at_version` | string | if deployed | Git version when deployed |
| `linters_pass` | bool | if code changed | Did all linters pass? |
| `linters_pass_at_version` | string | if linted | Git version when linted |
| `is_job_complete` | bool | yes | Is the job ACTUALLY done? |
| `what_remains` | string | yes | Must be "none" to allow stop |

## Example: Code Changes Session

```json
{
  "self_report": {
    "code_changes_made": true,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "deployed": true,
    "deployed_at_version": "abc1234",
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Fixed CORS config, deployed to staging, verified login flow",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/dashboard"],
    "console_clean": true
  }
}
```

## Example: No Code Changes Session

```json
{
  "self_report": {
    "code_changes_made": false,
    "web_testing_done": true,
    "web_testing_done_at_version": "abc1234",
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Reset 191 CVs to pending status via SQL",
    "what_remains": "none"
  },
  "evidence": {
    "urls_tested": ["https://staging.example.com/candidates"],
    "console_clean": true
  }
}
```

## Version Tracking

- Version-dependent fields must include `*_at_version` with git commit hash
- If code changes after setting a field, hooks automatically reset it to false
- Get current version: `git rev-parse --short HEAD`

## Web Smoke Artifacts

The stop hook validates `.claude/web-smoke/summary.json`:
- Must exist when `web_testing_done: true` is claimed
- Must show `passed: true`
- `tested_at_version` must match current git version

If artifacts pass, `web_testing_done` is auto-set to true.
