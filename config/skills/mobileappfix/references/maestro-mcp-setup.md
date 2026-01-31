# Maestro MCP Setup Guide

Complete setup instructions for the Maestro MCP server. This guide covers the forked Maestro with gRPC fixes required for reliable Android emulator connectivity.

## Overview

The RevOnc project uses a **forked Maestro** at `olivier-motium/Maestro` with critical fixes for MCP functionality:

| PR | Fix | Issue Addressed |
|----|-----|-----------------|
| #2934 | gRPC retry logic | UNAVAILABLE: io exception errors |
| #2935 | Auto-install driver APKs | Missing driver on device startup |

These PRs are merged in the `oli4-combined-fixes` branch but NOT yet in upstream Maestro.

## Prerequisites

1. **Java 11+** - Required for building Maestro
2. **Android SDK** - With platform-tools for adb
3. **Xcode** - For iOS simulator (macOS only)
4. **Git** - For cloning the fork

## Installation

### Step 1: Clone the Forked Maestro

```bash
cd ~/Desktop/motium_github
git clone https://github.com/olivier-motium/Maestro.git maestro-oli4
cd maestro-oli4
git checkout oli4-combined-fixes
```

### Step 2: Build Maestro CLI

```bash
./gradlew :maestro-cli:installDist
```

This creates the binary at:
```
maestro-cli/build/install/maestro/bin/maestro
```

### Step 3: Configure MCP in Project

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "maestro-oli4-mcp": {
      "command": "/Users/YOUR_USERNAME/Desktop/motium_github/maestro-oli4/maestro-cli/build/install/maestro/bin/maestro",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

**IMPORTANT**: Replace `YOUR_USERNAME` with your actual username.

### Step 4: Restart Claude Code

The MCP server only loads on session start. After adding the config, restart Claude Code.

## Android-Specific Setup

**CRITICAL**: Android emulators require additional manual setup that the MCP doesn't auto-provision.

### Required: Install Maestro Driver APKs

Before using Maestro MCP with Android, install the driver packages:

```bash
# Set ADB path
ADB=$HOME/Library/Android/sdk/platform-tools/adb

# List connected devices
$ADB devices

# Install both driver APKs (from the built Maestro)
MAESTRO_DIR=~/Desktop/motium_github/maestro-oli4
$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-server.apk
$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-app.apk

# Verify installation
$ADB shell pm list packages | grep maestro
# Should show: package:dev.mobile.maestro and package:dev.mobile.maestro.test
```

### Required: Start Instrumentation Service

After installing APKs, start the driver service:

```bash
$ADB shell am instrument -w dev.mobile.maestro.test/androidx.test.runner.AndroidJUnitRunner &
```

### Required: Set Up Port Forwarding

```bash
$ADB forward tcp:7001 tcp:7001
```

### Convenience Script

Create a setup script for quick Android initialization:

```bash
#!/bin/bash
# save as: setup-maestro-android.sh

ADB=$HOME/Library/Android/sdk/platform-tools/adb
MAESTRO_DIR=~/Desktop/motium_github/maestro-oli4

echo "Installing Maestro driver APKs..."
$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-server.apk
$ADB install -r $MAESTRO_DIR/maestro-client/build/resources/main/maestro-app.apk

echo "Setting up port forwarding..."
$ADB forward tcp:7001 tcp:7001

echo "Starting instrumentation service..."
$ADB shell am instrument -w dev.mobile.maestro.test/androidx.test.runner.AndroidJUnitRunner &

sleep 3
echo "Maestro Android setup complete!"
```

## iOS Setup

iOS simulators generally work out of the box. No additional setup required beyond having Xcode installed.

## Verifying the Setup

### 1. Check MCP Tools Available

In Claude Code, use ToolSearch:
```
ToolSearch(query: "maestro")
```

Should return tools like:
- `mcp__maestro-oli4-mcp__list_devices`
- `mcp__maestro-oli4-mcp__run_flow`
- `mcp__maestro-oli4-mcp__take_screenshot`
- `mcp__maestro-oli4-mcp__inspect_view_hierarchy`

### 2. List Devices

```
mcp__maestro-oli4-mcp__list_devices()
```

Should show connected simulators/emulators with `"connected": true`.

### 3. Take Test Screenshot

```
mcp__maestro-oli4-mcp__take_screenshot(device_id: "emulator-5554")
```

Should return an image of the device screen.

## Troubleshooting

### Error: "UNAVAILABLE: io exception"

**Cause**: gRPC channel to Maestro driver failed.

**Fix**:
1. Check if driver APKs are installed: `adb shell pm list packages | grep maestro`
2. If not installed, follow "Install Maestro Driver APKs" above
3. Restart instrumentation service
4. Verify port forwarding is active

### Error: "DEADLINE_EXCEEDED"

**Cause**: gRPC connection timed out waiting for driver.

**Fix**:
1. Ensure emulator is fully booted (not stuck on boot animation)
2. Re-run the full Android setup script
3. Try cold booting the emulator

### Error: "No tools found" for Maestro

**Cause**: MCP server not connected.

**Fix**:
1. Verify `.mcp.json` has correct path to maestro binary
2. Ensure the binary exists and is executable
3. Restart Claude Code session
4. Check for errors in Claude Code startup logs

### Error: "Failed to take screenshot" immediately after setup

**Cause**: Instrumentation service not fully started.

**Fix**: Wait 3-5 seconds after starting instrumentation, then retry.

### Emulator shows in list but commands fail

**Cause**: Driver installed but port forwarding missing.

**Fix**:
```bash
$ADB forward tcp:7001 tcp:7001
```

## Tool Reference

The actual MCP tool names (note the `oli4` suffix):

| Tool | Purpose |
|------|---------|
| `mcp__maestro-oli4-mcp__list_devices` | List available simulators/emulators |
| `mcp__maestro-oli4-mcp__start_device` | Start a simulator/emulator |
| `mcp__maestro-oli4-mcp__run_flow` | Execute inline Maestro commands |
| `mcp__maestro-oli4-mcp__run_flow_files` | Execute Maestro flow YAML files |
| `mcp__maestro-oli4-mcp__take_screenshot` | Capture device screen |
| `mcp__maestro-oli4-mcp__inspect_view_hierarchy` | Get UI element tree |
| `mcp__maestro-oli4-mcp__tap_on` | Tap UI element |
| `mcp__maestro-oli4-mcp__input_text` | Enter text |
| `mcp__maestro-oli4-mcp__launch_app` | Launch application |
| `mcp__maestro-oli4-mcp__back` | Press back button |
| `mcp__maestro-oli4-mcp__cheat_sheet` | Get Maestro command reference |

## Updating the Fork

To pull latest upstream changes and merge with fixes:

```bash
cd ~/Desktop/motium_github/maestro-oli4
git fetch upstream
git checkout oli4-combined-fixes
git merge upstream/main
# Resolve conflicts if any
./gradlew :maestro-cli:installDist
```

## Why a Fork?

The upstream Maestro MCP has issues connecting to Android emulators:

1. **No driver auto-installation** - The MCP assumes drivers are installed but doesn't install them
2. **No gRPC retry** - Connection failures are fatal instead of retried
3. **No channel recreation** - Once a gRPC channel fails, it stays dead

Our fork (PRs #2934 and #2935) addresses these issues. Until merged upstream, we use this fork.
