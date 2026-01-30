# Harness Test Case Schema

This document describes the JSON schema for harness test cases.

## Location

Test case files are stored in:
```
~/.claude/skills/harness-test/test-cases/*.json
```

## Schema

```json
{
  "name": "string (required)",
  "description": "string (required)",
  "type": "string (optional): hook | skill | settings",
  "target": "string (optional): path to the file being tested",
  "setup": {
    "state_file": "string (optional): name of state file to create",
    "state_content": "object (optional): JSON content for state file",
    "files": "object (optional): files to create { path: content }"
  },
  "prompt": "string (required): prompt to send to Claude",
  "assertions": [
    {
      "type": "string (required): assertion type",
      "...": "additional fields based on type"
    }
  ],
  "timeout": "number (optional): timeout in seconds, default 120"
}
```

## Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier for the test (matches filename without .json) |
| `description` | string | Human-readable description of what is being tested |
| `prompt` | string | The prompt to send to Claude in the sandbox |
| `assertions` | array | List of assertions to verify after execution |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | - | Category: "hook", "skill", or "settings" |
| `target` | string | - | Path to the file being tested (for documentation) |
| `setup` | object | {} | Pre-test setup configuration |
| `timeout` | number | 120 | Maximum time in seconds for test execution |

## Setup Object

The `setup` object configures the sandbox before running the test:

```json
{
  "state_file": "forge-state.json",
  "state_content": {
    "iteration": 1,
    "plan_mode_completed": false
  },
  "files": {
    "src/main.py": "# existing content",
    "config.json": "{\"key\": \"value\"}"
  }
}
```

| Field | Description |
|-------|-------------|
| `state_file` | Name of file to create in `.claude/` directory |
| `state_content` | JSON object to write to state file |
| `files` | Map of file paths to content (relative to project root) |

## Assertion Types

### file_exists

Assert that a file was created.

```json
{
  "type": "file_exists",
  "path": "src/test.py"
}
```

### file_not_exists

Assert that a file was NOT created (for testing blocking behavior).

```json
{
  "type": "file_not_exists",
  "path": "src/blocked.py"
}
```

### file_contains

Assert that a file contains a pattern.

```json
{
  "type": "file_contains",
  "path": "src/test.py",
  "pattern": "def hello"
}
```

### output_contains

Assert that stdout or stderr contains a pattern.

```json
{
  "type": "output_contains",
  "pattern": "PLAN MODE REQUIRED"
}
```

### output_not_contains

Assert that stdout and stderr do NOT contain a pattern.

```json
{
  "type": "output_not_contains",
  "pattern": "permission denied"
}
```

### state_field

Assert that a state file field has a specific value.

```json
{
  "type": "state_field",
  "file": "forge-state.json",
  "field": "iteration",
  "expected": "1"
}
```

### exit_code

Assert that Claude exited with a specific code.

```json
{
  "type": "exit_code",
  "code": 0
}
```

## Example Test Case

```json
{
  "name": "plan-mode-enforcer-blocks-code-write",
  "description": "Verify Edit/Write blocked when plan_mode_completed=false",
  "type": "hook",
  "target": "config/hooks/plan-mode-enforcer.py",
  "setup": {
    "state_file": "forge-state.json",
    "state_content": {
      "iteration": 1,
      "plan_mode_completed": false,
      "started_at": "2026-01-30T12:00:00Z"
    },
    "files": {
      "src/main.py": "# existing file"
    }
  },
  "prompt": "Use the Write tool to write 'print(\"test\")' to src/test.py",
  "assertions": [
    {
      "type": "file_not_exists",
      "path": "src/test.py"
    },
    {
      "type": "output_contains",
      "pattern": "PLAN MODE"
    }
  ],
  "timeout": 60
}
```

## Best Practices

1. **Name tests descriptively**: Use kebab-case, include the hook/skill name and behavior
2. **Test one thing**: Each test should verify a single behavior
3. **Set up minimal state**: Only create files/state needed for the test
4. **Use specific patterns**: Avoid overly broad regex in assertions
5. **Set appropriate timeouts**: Hook tests can be fast (60s), skill tests may need more (120s+)
6. **Document the target**: Use `type` and `target` to help others understand what's being tested

## Adding New Test Cases

1. Create a new `.json` file in `test-cases/` directory
2. Name it `{hook-or-skill-name}-{behavior}.json`
3. Follow the schema above
4. Run `/harness-test --test your-test-name` to verify it works
