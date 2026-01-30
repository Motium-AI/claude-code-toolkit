---
name: repair
description: Unified debugging router that detects platform (web vs mobile) and routes to /appfix or /mobileappfix. Use when asked to "fix", "repair", "debug", or "/repair".
---

# Unified Repair Router (/repair)

**This skill routes to the appropriate debugging skill based on platform detection.**

## Overview

`/repair` is a unified entry point for debugging that automatically detects whether you're working on a web app or mobile app and routes to the appropriate skill:

- **Web apps** → `/appfix`
- **Mobile apps** → `/mobileappfix`

## Triggers

- `/repair`
- "repair the app"
- "fix it" (when context is ambiguous)

## Platform Detection

Analyze the user's prompt and project context to determine the platform:

### Mobile Indicators (→ /mobileappfix)

| Signal | Example |
|--------|---------|
| Keywords | "mobile", "iOS", "Android", "React Native", "Expo" |
| Tools | "Maestro", "simulator", "emulator", "TestFlight" |
| Files | `app.json`, `eas.json`, `metro.config.js` |
| Errors | "build failed", "pod install", "gradle" |

### Web Indicators (→ /appfix)

| Signal | Example |
|--------|---------|
| Keywords | "web", "browser", "staging", "production" |
| Tools | "Chrome", "DevTools", "console" |
| Errors | "CORS", "API", "network", "fetch failed" |
| Files | `next.config.js`, `vite.config.ts`, `.env.staging` |

## Routing Logic

```
/repair [description]
  │
  ├─ Check for explicit mobile keywords
  │   ├─ Found: mobile, iOS, Android, Maestro, simulator, React Native, Expo
  │   └─► Invoke: /mobileappfix
  │
  ├─ Check for explicit web keywords
  │   ├─ Found: web, browser, staging, CORS, API, Chrome
  │   └─► Invoke: /appfix
  │
  └─ Ambiguous or no clear signal
      └─► Ask user ONCE: "Is this a web app or mobile app?"
          ├─ Web → /appfix
          └─ Mobile → /mobileappfix
```

## Execution

**Step 1: Detect Platform**

Analyze the user's prompt for platform indicators:

```python
# Mobile patterns (case-insensitive)
MOBILE_PATTERNS = [
    r"\bmobile\b",
    r"\bios\b",
    r"\bandroid\b",
    r"\breact native\b",
    r"\bexpo\b",
    r"\bmaestro\b",
    r"\bsimulator\b",
    r"\bemulator\b",
    r"\btestflight\b",
    r"\bapp store\b",
    r"\bplay store\b",
    r"\bpod install\b",
    r"\bgradle\b",
    r"\bxcode\b",
]

# Web patterns (case-insensitive)
WEB_PATTERNS = [
    r"\bweb\b",
    r"\bbrowser\b",
    r"\bstaging\b",
    r"\bproduction\b",
    r"\bcors\b",
    r"\bapi\b",
    r"\bchrome\b",
    r"\bdevtools\b",
    r"\bconsole\b",
    r"\bfetch\b",
    r"\bnetwork\b",
]
```

**Step 2: Route to Skill**

Use the Skill tool to invoke the appropriate skill:

```
# If mobile detected:
Skill(skill="mobileappfix", args="$ARGUMENTS")

# If web detected:
Skill(skill="appfix", args="$ARGUMENTS")
```

**Step 3: Handle Ambiguity**

If no clear platform signal is detected, ask the user once:

```
AskUserQuestion(
  questions=[{
    "question": "Is this a web app or a mobile app?",
    "header": "Platform",
    "options": [
      {"label": "Web (browser-based)", "description": "Routes to /appfix for web debugging"},
      {"label": "Mobile (iOS/Android)", "description": "Routes to /mobileappfix for mobile debugging"}
    ],
    "multiSelect": false
  }]
)
```

Then route based on the answer.

## Examples

### Clear Mobile Signal
```
User: /repair the mobile app crashes on iOS
Action: → /mobileappfix
```

### Clear Web Signal
```
User: /repair staging is showing CORS errors
Action: → /appfix
```

### Ambiguous Signal
```
User: /repair the app is broken
Action: Ask "Is this a web app or mobile app?" then route accordingly
```

## Why /repair Exists

Before `/repair`, users had to remember:
- `/appfix` for web apps
- `/mobileappfix` for mobile apps

`/repair` provides a single unified entry point that handles the routing automatically, reducing cognitive load.

## Relationship to Other Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `/repair` | Router | When unsure which debugging skill to use |
| `/appfix` | Web debugging | When you know it's a web app |
| `/mobileappfix` | Mobile debugging | When you know it's a mobile app |
| `/forge` | Task execution | When implementing features, not debugging |
