# Mobile App Debugging Rubric

A structured approach to diagnosing and fixing mobile app issues. Use this rubric during the `/mobileappfix` workflow.

## Diagnosis Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  SYMPTOM IDENTIFICATION                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. CATEGORIZE THE SYMPTOM                                          │
│     ├─► App crash/freeze                                            │
│     ├─► UI not rendering                                            │
│     ├─► Navigation broken                                           │
│     ├─► Data not loading                                            │
│     ├─► Maestro test failing                                        │
│     └─► Build/compile error                                         │
│                                                                      │
│  2. COLLECT EVIDENCE                                                │
│     ├─► Maestro screenshots                                         │
│     ├─► Metro bundler logs                                          │
│     ├─► Native crash logs (Console.app / logcat)                    │
│     ├─► React Query devtools (if available)                         │
│     └─► Network requests (Flipper / React Native Debugger)          │
│                                                                      │
│  3. ISOLATE THE FAILURE                                             │
│     ├─► Which screen?                                               │
│     ├─► Which user action?                                          │
│     ├─► Which data state?                                           │
│     └─► Reproducible?                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Category 1: App Crash/Freeze

### Symptoms
- App closes unexpectedly
- UI freezes, unresponsive
- Blank white/black screen

### Diagnosis Steps

1. **Check Metro bundler**
   ```bash
   # Look for red error messages
   # Common: undefined is not an object
   # Common: Cannot read property 'x' of undefined
   ```

2. **Check native crash logs**
   ```bash
   # iOS
   open -a Console
   # Filter: revonc, crash

   # Android
   adb logcat -s AndroidRuntime:E
   ```

3. **Check for memory issues**
   ```bash
   # iOS: Look for "Memory pressure" in Console
   # Android: Look for "OutOfMemoryError" in logcat
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Null reference | "undefined is not an object" | Add null checks, optional chaining |
| Infinite loop | UI freeze, high CPU | Check useEffect dependencies |
| Memory leak | Slow degradation | Clean up subscriptions, timers |
| Native module crash | Crash without JS error | Check native logs, rebuild |

## Category 2: UI Not Rendering

### Symptoms
- Blank screen
- Loading spinner never stops
- Elements missing
- Wrong layout

### Diagnosis Steps

1. **Check component tree**
   ```typescript
   // Add console.log in render
   console.log("MyComponent rendering", { props, state });
   ```

2. **Check conditional rendering**
   ```typescript
   // Common issue: early return before data loads
   if (isLoading) return <Spinner />;
   if (!data) return null; // Never reaches actual content
   ```

3. **Check style issues**
   ```typescript
   // Common: height: 0, opacity: 0, position off-screen
   // Use: { borderWidth: 1, borderColor: 'red' } to debug
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Query not fetching | isLoading forever | Check query enabled condition |
| Wrong conditional | Component returns early | Verify if/else logic |
| Style issues | Element exists but invisible | Debug with borders |
| Key issues | Wrong elements render | Use unique keys in lists |

## Category 3: Navigation Broken

### Symptoms
- Redirect loops
- Wrong screen displayed
- Back button not working
- Deep link fails

### Diagnosis Steps

1. **Check navigation guards**
   ```typescript
   // util/guards/RequireAuth.tsx
   // Log auth state and redirects
   console.log("Guard check:", { isAuthenticated, programStatus });
   ```

2. **Check expo-router state**
   ```typescript
   import { usePathname, useSegments } from 'expo-router';
   console.log("Current path:", usePathname());
   console.log("Segments:", useSegments());
   ```

3. **Check auth decision tree**
   ```
   app/index.tsx:
   isLoading? → Spinner
   !isAuthenticated? → /(auth)
   programStatus === "NO_PROGRAM"? → /(onboarding)
   else → /(app)
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Guard timing | Flicker, wrong redirect | Add loading states |
| Stale auth state | Logged in but redirected | Check session query |
| Wrong route | Ends up in unexpected screen | Verify routing logic |
| Missing layout | Screen crashes | Check _layout.tsx files |

## Category 4: Data Not Loading

### Symptoms
- Empty lists
- Stale data
- "No data" message
- Infinite loading

### Diagnosis Steps

1. **Check React Query state**
   ```typescript
   const { data, isLoading, error, isError } = useQuery(...);
   console.log("Query state:", { data, isLoading, error });
   ```

2. **Check network requests**
   - Use Flipper or React Native Debugger
   - Check Network tab for requests
   - Verify response status and body

3. **Check Supabase queries**
   ```typescript
   const { data, error } = await supabase
     .from('table')
     .select('*');
   console.log("Supabase result:", { data, error });
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Query disabled | No network request | Check `enabled` option |
| Auth required | 401 error | Ensure session is passed |
| Wrong query key | Stale/wrong data | Verify query key factory |
| RLS policy | Empty array, no error | Check Supabase RLS |
| Cache not invalidating | Stale after mutation | Call invalidateQueries |

## Category 5: Maestro Test Failing

### Symptoms
- Element not found
- Assertion failed
- Timeout
- App crash during test

### Diagnosis Steps

1. **Check element detection**
   ```bash
   maestro hierarchy
   # Look for resource-id matching your testID
   ```

2. **Check screenshots**
   ```bash
   ls .maestro/screenshots/
   # Find the last screenshot before failure
   ```

3. **Check accessibility**
   ```typescript
   // TouchableWithoutFeedback breaks testID detection on iOS
   <TouchableWithoutFeedback accessible={false}>
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Missing testID | Element not in hierarchy | Add testID prop |
| Accessibility wrapper | All text merged | Add `accessible={false}` |
| Timing | Element not loaded yet | Increase timeout, add wait |
| Wrong selector | Finds nothing | Use `maestro hierarchy` to debug |
| Expo dev client | clearState fails | Use `clearState: false` |

## Category 6: Build/Compile Error

### Symptoms
- npm run ios fails
- Metro bundle error
- TypeScript error
- Pod install fails

### Diagnosis Steps

1. **Clean and rebuild**
   ```bash
   # JavaScript
   rm -rf node_modules .expo
   npm install
   npm start --reset-cache

   # iOS
   cd ios && rm -rf Pods Podfile.lock
   pod install && cd ..
   npm run ios

   # Android
   cd android && ./gradlew clean && cd ..
   npm run android
   ```

2. **Check TypeScript**
   ```bash
   npx tsc --noEmit
   # Fix all type errors
   ```

3. **Check ESLint**
   ```bash
   npm run lint
   # Fix all lint errors
   ```

### Common Causes & Fixes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Dependency mismatch | Version conflict | Delete node_modules, reinstall |
| Native cache | Old binaries | Clean build, rebuild native |
| Missing pod | iOS build fails | pod install |
| Type error | tsc fails | Fix TypeScript errors |
| Babel config | Metro fails | Check babel.config.js |

## Debugging Tools

### Metro Bundler

```bash
# Start with fresh cache
npm start --reset-cache

# Enable verbose logging
npm start -- --verbose
```

### React Native Debugger

```bash
# Install
brew install --cask react-native-debugger

# Open and connect
open "rndebugger://set-debugger-loc?host=localhost&port=8081"
```

### Flipper

```bash
# Install
brew install --cask flipper

# Useful plugins:
# - Network
# - React DevTools
# - Databases (AsyncStorage)
```

### iOS Console

```bash
# Open Console.app
open -a Console

# Filter by process: revonc
# Filter by type: error, fault
```

### Android Logcat

```bash
# All React Native logs
adb logcat -s ReactNative:V ReactNativeJS:V

# Crashes only
adb logcat -s AndroidRuntime:E

# Clear and follow
adb logcat -c && adb logcat
```

## Fix Verification Checklist

Before marking a fix complete:

- [ ] Root cause identified and documented
- [ ] Fix applied with minimal changes
- [ ] Linters pass: `npm run lint && npm run typecheck`
- [ ] Unit tests pass: `npm run test:run`
- [ ] Maestro smoke test passes: `maestro test .maestro/journeys/J2-*.yaml`
- [ ] Screenshots captured as evidence
- [ ] Changes committed with descriptive message

## Anti-Patterns to Avoid

1. **Symptom masking**
   - DON'T: Add try/catch that swallows errors
   - DO: Fix the underlying cause

2. **Excessive null checks**
   - DON'T: Add `?.` everywhere
   - DO: Ensure data is loaded before accessing

3. **Force updates**
   - DON'T: Add `key={Math.random()}` to force re-render
   - DO: Fix the state/prop flow

4. **Timeout band-aids**
   - DON'T: Add `setTimeout` to "fix" timing issues
   - DO: Use proper async/await, loading states

5. **Ignoring warnings**
   - DON'T: Suppress warnings without understanding
   - DO: Fix the root cause of warnings
