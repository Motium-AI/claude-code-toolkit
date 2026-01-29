# Mobile App Topology

This file documents the mobile application configuration for the `/mobileappfix` workflow.

**IMPORTANT**: Fill this out before using `/mobileappfix`. The workflow needs this configuration to run tests and verify fixes.

## App Configuration

### Basic Info

| Property | Value |
|----------|-------|
| App Name | `RevOnc` |
| App ID (iOS) | `be.revonc.mobileapp` |
| App ID (Android) | `be.revonc.mobileapp` |
| Framework | React Native / Expo SDK 52 |
| Bundler | Metro |

### Project Paths

| Path | Purpose |
|------|---------|
| Project Root | `/Users/olivierdebeufderijcker/Desktop/motium_github/revonc/revonc-app` |
| Maestro Tests | `.maestro/` |
| iOS Native | `ios/` |
| Android Native | `android/` |

## Development Commands

### Daily Development

```bash
# Start Metro bundler
npm start

# Run on iOS Simulator
npm run ios

# Run on Android Emulator
npm run android

# Clear cache and restart
npm run start:clear
```

### Native Builds

```bash
# Regenerate native directories (after app.config.js changes)
npm run prebuild:clean
cd ios && pod install && cd ..

# Fresh iOS build
npm run ios

# Fresh Android build
npm run android
```

### EAS Cloud Builds

```bash
# Development build (for Maestro testing)
eas build --profile development --platform ios

# Preview build (internal testing)
eas build --profile preview

# Production build
eas build --profile production
```

## Maestro E2E Testing

### Configuration

```yaml
# .maestro/config.yaml
appId: be.revonc.mobileapp
timeout: 60000
screenshots: .maestro/screenshots

env:
  TEST_USER_EMAIL: oddr@revonc.be
  TEST_USER_PASSWORD: ${MAESTRO_TEST_PASSWORD}
```

### Test Commands

```bash
# Full test suite
npm run e2e
# or: maestro test .maestro/suite.yaml

# Quick smoke test (login flow)
maestro test .maestro/journeys/J2-returning-user-login.yaml

# Record new test
npm run e2e:record

# Debug element detection
maestro hierarchy
```

### Test Organization

| Category | Path | Purpose |
|----------|------|---------|
| Journeys | `.maestro/journeys/` | User journey tests (J1-J5) |
| Negative | `.maestro/negative/` | Error path tests (N1-N3) |
| Flows | `.maestro/flows/` | Reusable helper flows |
| Audit | `.maestro/audit/` | Visual UI audits |

### Key Journeys

| Journey | File | Tests |
|---------|------|-------|
| J1 | `J1-new-user-onboarding.yaml` | Register → Onboarding → App |
| J2 | `J2-returning-user-login.yaml` | Login → Main App (smoke) |
| J3 | `J3-main-app-navigation.yaml` | Navigate all tabs/screens |
| J4 | `J4-exercise-completion.yaml` | Complete exercise session |
| J5 | `J5-profile-settings.yaml` | Profile & settings |

## Simulator/Emulator Setup

### iOS Simulators

```bash
# List available simulators
xcrun simctl list devices available

# Boot specific simulator
xcrun simctl boot "iPhone 15 Pro"

# Open Simulator app
open -a Simulator

# Install app on booted simulator
xcrun simctl install booted ./path/to/app.app
```

### Android Emulators

```bash
# Set environment (add to ~/.zshrc)
export ANDROID_HOME=$HOME/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools

# List available AVDs
$ANDROID_HOME/emulator/emulator -list-avds

# Start emulator
$ANDROID_HOME/emulator/emulator -avd Medium_Phone_API_36 &

# Check connected devices
adb devices
```

### Available AVDs (This System)

- `Medium_Phone_API_36`
- `Pixel_Tablet`

## Log Sources

### Metro Bundler

```bash
# Logs visible in terminal where npm start runs
# Look for:
# - JavaScript errors (red text)
# - Bundle build failures
# - Transform errors
```

### iOS Console Logs

```bash
# Open Console.app
open -a Console

# Filter by app name: "revonc"
# Look for:
# - Native crashes
# - Memory warnings
# - Network errors
```

### Android Logcat

```bash
# All logs from device
adb logcat

# React Native specific
adb logcat -s ReactNative:V ReactNativeJS:V

# Crashes only
adb logcat -s AndroidRuntime:E
```

## Backend Dependencies

### API Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| Supabase | `<project>.supabase.co` | Auth, Database |
| RevOnc Engine | `https://revonc-engine-prod-*.run.app` | Program generation |

### Health Checks

```bash
# Supabase health (via app)
# Check network tab in React Native Debugger

# Engine health
curl -sf https://revonc-engine-prod-584724323433.europe-west1.run.app/health
```

## TestID Conventions

| Pattern | Example | Usage |
|---------|---------|-------|
| `{screen}_screen` | `profile_screen` | Screen containers |
| `{screen}_{element}` | `profile_settings_button` | Interactive elements |
| `auth_{action}_{element}` | `auth_login_submit_button` | Auth screens |
| `stepping_stone_{id}_{status}` | `stepping_stone_abc_current` | Dynamic elements |

## Critical Paths to Verify

After any fix, these flows must work:

1. **Login Flow**: Open app → Login → See stepping stones
2. **Exercise Start**: Tap current stone → Select training → Start exercise
3. **Profile Access**: Navigate to profile tab → See user stats
4. **Settings**: Open settings → Logout works

## Environment Variables

Required for E2E testing:

```bash
# .env (gitignored)
TEST_USER_EMAIL=oddr@revonc.be
TEST_USER_PASSWORD=<password>
EXPO_PUBLIC_IS_TEST_MODE=true

# Export for Maestro
export MAESTRO_TEST_PASSWORD=<password>
```

## Notes

- Expo dev builds don't support `clearState: true` in Maestro
- Always use `clearState: false` for development testing
- TestIDs may not work if wrapped in TouchableWithoutFeedback (add `accessible={false}`)
- iOS builds require Xcode 15+ with iOS 17+ SDK
- Android builds require Android SDK 34+

## Expo Dev Client + Maestro: Auto-Connect Solution

**Issue:** The Expo Dev Client launcher has a merged accessibility tree that makes automated taps unreliable.

**Solution:** Use deep linking to auto-connect to Metro, bypassing the launcher UI.

### Recommended: Use run-e2e.sh Script

```bash
# Auto-connects to Metro and runs tests
./scripts/run-e2e.sh .maestro/journeys/J2-returning-user-login.yaml
```

The script:
1. Starts Metro if not running
2. Boots iOS simulator if needed
3. Launches app via deep link: `exp+revonc://expo-development-client/?url=http://localhost:8081`
4. Runs Maestro tests

### Manual Alternative

```bash
# Start Metro
npm start &

# Wait for Metro, then connect app via deep link
xcrun simctl openurl booted "exp+revonc://expo-development-client/?url=http://localhost:8081"

# Run tests (app already connected)
maestro test .maestro/journeys/J2-returning-user-login.yaml
```

### Deep Link Format

```
exp+{app-slug}://expo-development-client/?url={metro-url}
```

For RevOnc: `exp+revonc://expo-development-client/?url=http://localhost:8081`
