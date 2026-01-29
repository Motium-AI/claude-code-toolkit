---
name: revonc-eas-deploy
description: RevOnc mobile app EAS deployment guide. Build, deploy, and publish OTA updates for iOS/Android via Expo Application Services. Use for "/eas", "deploy to testflight", "push ota update", or "build ios/android".
---

# RevOnc EAS Deployment

Complete guide for deploying the RevOnc mobile app through EAS (Expo Application Services).

## Account & Project Identity

| Property | Value |
|----------|-------|
| **Account** | `revonc` |
| **Project** | `@revonc/RevOnc` |
| **Project ID** | `2c936c80-d59b-480b-aad7-77fcba4c01cf` |
| **EAS CLI Version** | 16.16.0+ required |

### Dashboard Links

| Resource | URL |
|----------|-----|
| **Project Dashboard** | https://expo.dev/accounts/revonc/projects/RevOnc |
| **Builds** | https://expo.dev/accounts/revonc/projects/RevOnc/builds |
| **Updates** | https://expo.dev/accounts/revonc/projects/RevOnc/updates |

---

## Build Profiles Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EAS BUILD PROFILES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  development          preview            testflight-internal    testflight  │
│  ┌──────────┐        ┌──────────┐        ┌──────────────┐       ┌─────────┐│
│  │ Simulator│        │ Internal │        │   Internal   │       │External ││
│  │ + Debug  │        │   QA     │        │ Beta Testers │       │  Beta   ││
│  │ Client   │        │          │        │ (staging)    │       │ (prod)  ││
│  └──────────┘        └──────────┘        └──────────────┘       └─────────┘│
│                                                                              │
│  Channel:            Channel:            Channel:               Channel:     │
│  development         preview             staging                production   │
│                                                                              │
│  Purpose:            Purpose:            Purpose:               Purpose:     │
│  - Local dev         - APK/IPA QA        - Revonc_team (5)      - Pilot (102)│
│  - Metro bundler     - Internal test     - Test OTA first       - Production │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Profile | Distribution | Channel | iOS | Android | Purpose |
|---------|-------------|---------|-----|---------|---------|
| `development` | Internal | `development` | Simulator | APK | Local debugging |
| `development:device` | Internal | `development` | Device | APK | Physical device debugging |
| `local` | Internal | — | Simulator | APK | Fast local builds (no channel) |
| `preview` | Internal | `preview` | Default | Default | Internal QA |
| `testflight-internal` | **Store** | `staging` | — | — | Internal beta (Revonc_team) |
| `testflight` | **Store** | `production` | — | — | External beta (Pilot) |
| `production` | — | `production` | — | App Bundle | Store release |

---

## Quick Commands

### Check Status

```bash
# Account info
eas whoami

# Project info
eas project:info

# List recent builds
eas build:list --limit 10

# List channels
eas channel:list

# List updates on a branch
eas update:list --branch production --limit 5
```

### Build Commands

```bash
# Internal testing (Revonc_team) - staging channel
eas build --profile testflight-internal --platform ios --auto-submit

# External testing (Pilot) - production channel
eas build --profile testflight --platform ios --auto-submit

# Preview APK for Android QA
eas build --profile preview --platform android

# Production release
eas build --profile production
eas submit --profile production
```

### OTA Updates (Over-The-Air)

```bash
# Push to internal testers first (Revonc_team)
eas update --channel staging --message "description"

# Push to production after verification (Pilot + App Store)
eas update --channel production --message "description"

# Rollback if needed
eas update:rollback --channel production
```

---

## TestFlight Distribution

### Two-Channel Strategy

| Profile | Channel | TestFlight Group | Purpose |
|---------|---------|------------------|---------|
| `testflight-internal` | `staging` | Revonc_team (5 internal) | Test OTA updates first |
| `testflight` | `production` | Pilot (102 external) | Stable, verified updates |

### Staged Publishing Workflow

```
1. Push to staging    → eas update --channel staging --message "..."
   └─► Revonc_team (5 internal testers) receives update

2. Verify update works (test in app)

3. Push to production → eas update --channel production --message "..."
   └─► Pilot (102 external testers) + App Store users receive update
```

### Build & Submit Commands

```bash
# Build for internal TestFlight (staging channel)
eas build --profile testflight-internal --platform ios --auto-submit

# Build for external TestFlight (production channel)
eas build --profile testflight --platform ios --auto-submit
```

---

## Channel vs Profile Names

⚠️ **CRITICAL: Profile names ≠ Channel names**

```
Build Profile          → Embedded Channel
─────────────────────────────────────────
development            → development
preview                → preview
testflight-internal    → staging
testflight             → production     ← NOT "testflight"!
production             → production
```

**WRONG:**
```bash
eas update --channel testflight --message "Fix"  # Creates orphan updates!
```

**CORRECT:**
```bash
eas update --channel production --message "Fix"  # TestFlight + App Store receive
```

---

## OTA vs App Store Releases

| Change Type | Method | Command |
|-------------|--------|---------|
| Bug fix (JS only) | OTA | `eas update --channel production` |
| New feature (JS only) | OTA | `eas update --channel production` |
| New native module | App Store | `eas build --profile testflight` |
| SDK upgrade | App Store | `eas build --profile testflight` |
| App icon/splash change | App Store | `eas build --profile testflight` |

---

## App Configuration

Current values from `app.config.js`:

| Property | iOS | Android |
|----------|-----|---------|
| **Bundle ID / Package** | `be.revonc.mobileapp` | `be.revonc.mobileapp` |
| **Version** | `1.0.0` | `1.0.0` |
| **Build Number** | `102` (manual increment) | Version Code: `18` |
| **Apple Team ID** | `J6V6MWLU44` | — |
| **Expo SDK** | `52.0.48` | `52.0.48` |
| **Runtime Version** | `1.0.0` | `1.0.0` |

### Incrementing Build Number

For new TestFlight submissions, increment `buildNumber` in `app.config.js`:

```javascript
ios: {
  // Build 102 submitted Jan 29, 2026. Increment manually for new TestFlight builds.
  buildNumber: "103",  // ← Increment this
}
```

---

## Local TestFlight Builds (Free)

Build and submit to TestFlight without EAS costs (requires Mac with Xcode):

```bash
# Automated script
./scripts/deploy-testflight.sh

# Skip prebuild for faster rebuilds
./scripts/deploy-testflight.sh --skip-prebuild
```

### First-Time Setup

1. Create App Store Connect API Key (appstoreconnect.apple.com → Users and Access → Keys)
2. Download `.p8` file to `~/.appstoreconnect/private_keys/`
3. Create `.env.local` with credentials:

```bash
API_KEY_ID=your-key-id-here
API_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APPLE_TEAM_ID=your-team-id-here
```

⚠️ **WARNING:** Local builds do NOT embed EAS channels. Users on local builds cannot receive OTA updates!

---

## Submit Configuration

### iOS (App Store Connect)

| Apple ID | ASC App ID |
|----------|------------|
| `tech@revonc.be` | `6752873821` |

### Android (Play Store)

| Service Account | Track |
|-----------------|-------|
| `./service-account-file.json` | `internal` |

---

## Troubleshooting

### OTA Updates Not Received

1. Verify channel in `eas.json` matches update target
2. Check runtime version compatibility (`1.0.0`)
3. Have users close app completely and reopen twice

### Build Failures

```bash
# Clear EAS cache
eas build --clear-cache --profile <profile> --platform <platform>

# Check build logs
eas build:view <build-id>
```

### Credential Issues

```bash
# Re-configure credentials
eas credentials --platform ios
eas credentials --platform android
```

### Users Not Getting Updates

1. Check if binary was built with correct channel:
   - EAS build → has channel → receives OTA
   - Local build → NO channel → cannot receive OTA
2. Verify user is on correct TestFlight group
3. Check `eas update:list --branch production`

---

## Pre-Deployment Checklist

```markdown
## RevOnc Mobile Release Checklist

### Code Readiness
- [ ] All tests pass: npm run test:run
- [ ] Linters pass: npm run lint && npm run typecheck
- [ ] No console errors in app

### Testing
- [ ] Feature tested on iOS Simulator
- [ ] Feature tested on Android Emulator
- [ ] OTA pushed to staging first
- [ ] Revonc_team verified update works

### Release
- [ ] Build number incremented (if new binary)
- [ ] Commit message clear
- [ ] OTA pushed to production
```

---

## Triggers

- `/eas`
- `/revonc-deploy`
- "deploy to testflight"
- "push ota update"
- "build ios"
- "build android"
- "publish to app store"
- "eas build"
- "eas update"
