# Maestro Smoke Test Contract

Defines the artifact schema for Maestro E2E test verification. The stop hook validates these artifacts exist and tests passed.

## Purpose

Maestro smoke tests prove the mobile app functions correctly after a fix. They verify actual user flows on simulator/emulator.

## Required Artifacts

After Maestro verification, the following must exist:

```
.claude/maestro-smoke/
├── summary.json          # Pass/fail + test results (REQUIRED)
├── screenshots/          # Test screenshots (REQUIRED)
│   ├── *.png
│   └── ...
└── output.log            # Maestro test output (optional)
```

## summary.json Schema

```json
{
  "passed": true,
  "tested_at": "2026-01-28T10:00:00Z",
  "tested_at_version": "abc1234",
  "platform": "ios",
  "device": "iPhone 15 Pro Simulator",
  "app_id": "be.revonc.mobileapp",
  "maestro_version": "1.38.0",
  "flows_executed": [
    {
      "name": "J2-returning-user-login.yaml",
      "path": ".maestro/journeys/J2-returning-user-login.yaml",
      "passed": true,
      "duration_ms": 45000,
      "screenshots": [
        "j2_01_app_launched.png",
        "j2_07_stepping_stones_visible.png"
      ]
    }
  ],
  "total_flows": 1,
  "passed_flows": 1,
  "failed_flows": 0,
  "total_screenshots": 8,
  "error_message": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passed` | bool | yes | Overall pass/fail |
| `tested_at` | string | yes | ISO 8601 timestamp |
| `tested_at_version` | string | yes | Git commit hash when tested |
| `platform` | string | yes | "ios" or "android" |
| `device` | string | yes | Device/simulator name |
| `app_id` | string | yes | Application bundle ID |
| `flows_executed` | array | yes | Individual flow results |
| `total_flows` | int | yes | Number of flows run |
| `passed_flows` | int | yes | Flows that passed |
| `failed_flows` | int | yes | Flows that failed |
| `error_message` | string | no | Error details if failed |

### Flow Object Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Flow filename |
| `path` | string | yes | Full path to flow file |
| `passed` | bool | yes | Whether flow passed |
| `duration_ms` | int | no | Execution time |
| `screenshots` | array | yes | Screenshots captured |
| `error` | string | no | Error if failed |
| `failed_at_step` | string | no | Step that failed |

## Pass Conditions

The stop hook requires ALL of these:

1. `passed: true`
2. `total_flows >= 1` (at least one flow executed)
3. `failed_flows == 0`
4. `tested_at_version == current_git_version` (not stale)
5. Screenshots directory exists and contains files

## Checkpoint Integration

The checkpoint must include Maestro test fields:

```json
{
  "self_report": {
    "maestro_tests_passed": true,
    "maestro_tests_passed_at_version": "abc1234"
  },
  "evidence": {
    "maestro_flows_tested": [
      "J2-returning-user-login.yaml"
    ],
    "screenshots": [
      ".claude/maestro-smoke/screenshots/j2_07_stepping_stones_visible.png"
    ],
    "platform": "ios",
    "device": "iPhone 15 Pro Simulator"
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

## Creating Artifacts

### After Successful Maestro Run

```bash
#!/bin/bash
# create-maestro-artifacts.sh

mkdir -p .claude/maestro-smoke/screenshots

# Copy Maestro screenshots
cp -r .maestro/screenshots/* .claude/maestro-smoke/screenshots/ 2>/dev/null || true

# Get test info
VERSION=$(git rev-parse --short HEAD)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PLATFORM="${1:-ios}"
DEVICE="${2:-iPhone 15 Pro Simulator}"

# Create summary
cat > .claude/maestro-smoke/summary.json << EOF
{
  "passed": true,
  "tested_at": "$TIMESTAMP",
  "tested_at_version": "$VERSION",
  "platform": "$PLATFORM",
  "device": "$DEVICE",
  "app_id": "be.revonc.mobileapp",
  "flows_executed": [
    {
      "name": "J2-returning-user-login.yaml",
      "path": ".maestro/journeys/J2-returning-user-login.yaml",
      "passed": true,
      "screenshots": $(ls .claude/maestro-smoke/screenshots/*.png 2>/dev/null | jq -R -s 'split("\n") | map(select(length > 0) | split("/") | .[-1])')
    }
  ],
  "total_flows": 1,
  "passed_flows": 1,
  "failed_flows": 0
}
EOF

echo "Maestro artifacts created in .claude/maestro-smoke/"
```

### After Failed Maestro Run

```bash
#!/bin/bash
# create-maestro-failure-artifacts.sh

mkdir -p .claude/maestro-smoke/screenshots

# Copy any screenshots captured before failure
cp -r .maestro/screenshots/* .claude/maestro-smoke/screenshots/ 2>/dev/null || true

# Get info
VERSION=$(git rev-parse --short HEAD)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ERROR_MSG="${1:-Test failed}"

# Create summary with failure
cat > .claude/maestro-smoke/summary.json << EOF
{
  "passed": false,
  "tested_at": "$TIMESTAMP",
  "tested_at_version": "$VERSION",
  "platform": "ios",
  "device": "iPhone 15 Pro Simulator",
  "app_id": "be.revonc.mobileapp",
  "flows_executed": [
    {
      "name": "J2-returning-user-login.yaml",
      "path": ".maestro/journeys/J2-returning-user-login.yaml",
      "passed": false,
      "error": "$ERROR_MSG"
    }
  ],
  "total_flows": 1,
  "passed_flows": 0,
  "failed_flows": 1,
  "error_message": "$ERROR_MSG"
}
EOF

echo "Maestro failure artifacts created in .claude/maestro-smoke/"
```

## Minimum Required Flows

For a quick smoke test, at minimum run:

1. **J2-returning-user-login.yaml** - Verifies login and main app access

For more thorough verification:

1. J2 - Login flow
2. J3 - Navigation
3. J5 - Profile/settings

For complete verification:

- All journeys (J1-J5)
- Negative tests (N1-N3)

## Screenshot Requirements

Screenshots must capture:

1. **Initial state** - App launched
2. **Post-login** - Main screen visible
3. **Key UI elements** - Stepping stones, profile, etc.

Naming convention: `{journey}_{step}_{description}.png`

Examples:
- `j2_01_app_launched.png`
- `j2_04_login_screen.png`
- `j2_07_stepping_stones_visible.png`

## Relationship to Unit Tests

| Aspect | Unit Tests | Maestro E2E |
|--------|-----------|-------------|
| **Purpose** | Test isolated functions | Test full user flows |
| **Scope** | Components, services | App on device |
| **Speed** | Fast (seconds) | Slow (minutes) |
| **Required** | Before commit | After fix complete |
| **Artifacts** | Jest coverage | Screenshots + summary |

Both are required. Unit tests catch logic errors; Maestro tests catch integration and UI issues.
