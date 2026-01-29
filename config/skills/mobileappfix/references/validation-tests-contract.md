# Validation Tests Contract

Defines the artifact schema for fix-specific validation tests. The stop hook validates these artifacts exist and all tests pass.

## Purpose

Web smoke tests prove "the app loads" but NOT "the fix worked." Validation tests prove the specific fix achieved its goal.

**Example:**
- Fix: Notes summarization pipeline
- Web smoke: Dashboard loads ✓
- Validation test: Werner Iwens' `bullhorn_notes_summary_json` is NOT NULL ✗
- Result: Fix DIDN'T WORK - caught by validation test

## Required Artifacts

After fix verification, the following must exist:

```
.claude/validation-tests/
├── summary.json          # Pass/fail + all test results (REQUIRED)
└── tests/                # Individual test results (optional)
    └── *.json
```

## summary.json Schema

```json
{
  "passed": true,
  "tested_at": "2026-01-27T10:00:00Z",
  "tested_at_version": "abc1234",
  "fix_description": "Notes summarization should populate bullhorn_notes_summary_json",
  "total_tests": 2,
  "passed_tests": 2,
  "failed_tests": 0,
  "tests": [
    {
      "id": "notes_summary_populated",
      "description": "Werner Iwens bullhorn_notes_summary_json NOT NULL",
      "type": "database_query",
      "expected": "NOT NULL",
      "actual": "{\"summary\": \"Werner is a senior consultant...\"}",
      "passed": true,
      "tested_at": "2026-01-27T10:30:00Z"
    },
    {
      "id": "api_returns_summary",
      "description": "GET /api/persons/123/notes returns summary field",
      "type": "api_response",
      "expected": "status=200, body_contains=summary",
      "actual": "status=200, body={\"summary\": \"...\"}",
      "passed": true,
      "tested_at": "2026-01-27T10:31:00Z"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passed` | bool | yes | Overall pass/fail (all tests must pass) |
| `tested_at` | string | yes | ISO 8601 timestamp |
| `tested_at_version` | string | yes | Git commit hash when tested |
| `fix_description` | string | yes | What the fix was supposed to achieve |
| `total_tests` | int | yes | Total number of tests defined |
| `passed_tests` | int | yes | Number of tests that passed |
| `failed_tests` | int | yes | Number of tests that failed |
| `tests` | array | yes | Individual test results |

### Test Object Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier for the test |
| `description` | string | yes | Human-readable description |
| `type` | string | yes | Test type (see below) |
| `expected` | string | yes | Expected outcome |
| `actual` | string | yes | Actual outcome observed |
| `passed` | bool | yes | Whether test passed |
| `tested_at` | string | no | When this test was run |
| `error` | string | no | Error message if failed |

## Supported Test Types

| Type | Description | Expected Format | How to Execute |
|------|-------------|-----------------|----------------|
| `database_query` | SQL query result | `NOT NULL`, `= value`, `CONTAINS x`, `> N` | Execute query, compare result |
| `api_response` | HTTP endpoint check | `status=200`, `body_contains=x` | curl/fetch endpoint |
| `page_content` | DOM text check | `CONTAINS "text"`, `NOT CONTAINS "error"` | Surf CLI or Chrome MCP |
| `page_element` | Element exists | `EXISTS selector` | Query selector |
| `file_content` | File contains pattern | `MATCHES regex` | Read file, regex match |
| `command_output` | CLI command result | `CONTAINS "OK"`, `EXIT_CODE=0` | Run command |
| `log_absence` | No error in logs | `NOT_CONTAINS "error pattern"` | Logfire/log query |
| `count_check` | Numeric comparison | `>= N`, `== N`, `< N` | Query returns count |

## Pass Conditions

The stop hook requires ALL of these:

1. `passed: true`
2. `total_tests >= 1` (at least one test defined)
3. `failed_tests == 0`
4. `tested_at_version == current_git_version` (not stale)

## Checkpoint Integration

The checkpoint must include validation test fields:

```json
{
  "self_report": {
    "validation_tests_defined": true,
    "validation_tests_passed": true,
    "validation_tests_passed_at_version": "abc1234"
  },
  "validation_tests": {
    "tests": [...],
    "summary": {
      "total": 2,
      "passed": 2,
      "failed": 0,
      "last_run_version": "abc1234"
    }
  }
}
```

## Staleness Detection

Artifacts become stale when code changes after verification:

```
tested_at_version: abc1234
current_version:   def5678  <- Different!
-> STALE: Must re-verify
```

The stop hook automatically rejects stale artifacts and instructs re-verification.

## Example: Database Query Test

```bash
# Define the test in checkpoint
cat > .claude/completion-checkpoint.json << 'EOF'
{
  "validation_tests": {
    "tests": [{
      "id": "notes_populated",
      "description": "Werner Iwens has notes summary",
      "type": "database_query",
      "expected": "NOT NULL"
    }]
  }
}
EOF

# Execute the test
RESULT=$(psql $DATABASE_URL -t -c "SELECT bullhorn_notes_summary_json FROM persons WHERE person_id = 123")

# Check result
if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
  echo "PASSED: $RESULT"
  # Update checkpoint with passed: true, actual: "$RESULT"
else
  echo "FAILED: Value is NULL"
  # Update checkpoint with passed: false, actual: "NULL"
fi

# Create summary artifact
mkdir -p .claude/validation-tests
cat > .claude/validation-tests/summary.json << EOF
{
  "passed": true,
  "tested_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tested_at_version": "$(git rev-parse --short HEAD)",
  "fix_description": "Notes summarization pipeline",
  "total_tests": 1,
  "passed_tests": 1,
  "failed_tests": 0,
  "tests": [{
    "id": "notes_populated",
    "description": "Werner Iwens has notes summary",
    "type": "database_query",
    "expected": "NOT NULL",
    "actual": "$RESULT",
    "passed": true
  }]
}
EOF
```

## Example: API Response Test

```bash
# Execute API call
RESPONSE=$(curl -s -w "\n%{http_code}" https://staging.example.com/api/persons/123/notes)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS=$(echo "$RESPONSE" | tail -n 1)

# Check response
if [ "$STATUS" = "200" ] && echo "$BODY" | grep -q "summary"; then
  echo "PASSED: status=$STATUS, body contains summary"
  PASSED=true
else
  echo "FAILED: status=$STATUS or missing summary field"
  PASSED=false
fi
```

## Example: Page Content Test (Surf CLI)

```bash
# Navigate and check content
surf navigate "https://staging.example.com/persons/123"
CONTENT=$(surf page.text)

if echo "$CONTENT" | grep -q "Notes Summary"; then
  echo "PASSED: Page contains 'Notes Summary'"
else
  echo "FAILED: Page does not contain 'Notes Summary'"
fi
```

## When Tests Fail

**Failed tests surface issues that must be fixed!**

Do NOT:
- Claim completion with failed tests
- Skip tests because "the app works"
- Weaken expected values to make tests pass
- Remove failing tests

DO:
- Investigate WHY the test failed
- Fix the root cause
- Re-run the test
- Loop until ALL tests pass

## Relationship to Web Smoke

| Aspect | Web Smoke | Validation Tests |
|--------|-----------|------------------|
| **Purpose** | App loads without errors | Fix achieved its goal |
| **Scope** | Generic health | Fix-specific |
| **Required** | Always (appfix mode) | Always (appfix mode) |
| **Artifacts** | `.claude/web-smoke/` | `.claude/validation-tests/` |
| **Order** | After deploy | After deploy, before web smoke |

Both are required. Validation tests prove the fix works; web smoke proves the app still works.
