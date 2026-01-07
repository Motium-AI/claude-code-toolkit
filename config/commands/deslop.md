---
description: Exhaustive sweep to identify and remove AI-generated code slop
---

## Execution Strategy

**CRITICAL: Use plan mode and parallel agents for this audit.**

### Phase 1: Strategic Exploration (Plan Mode)
Use `EnterPlanMode` to research before generating findings. Launch up to 3 parallel `Task` agents with `subagent_type=Explore`:

**Agent 1 - Python Slop Scan:**
- Patterns 1-9: defensive checks, verbose variables, over-commented code
- Patterns: exception handling, string formatting, truthiness patterns
- Focus exclusively on .py files

**Agent 2 - React/TypeScript Slop Scan:**
- Patterns 10-20: null guards, memoization, verbose state, fragments
- Patterns: event handlers, type assertions, async patterns
- Focus on .tsx/.ts files

**Agent 3 - Cross-Language Patterns:**
- Patterns 21-25: comment slop, naming inconsistencies, dead code
- Patterns: excessive logging, error message verbosity
- Scan both Python and TypeScript files

### Phase 2: Synthesis
After agents return, synthesize findings in the plan file:
- Compare file-local conventions vs flagged patterns (avoid false positives)
- Identify patterns that could be added to linter rules
- Rank files by slop density for cleanup priority

### Phase 3: Report Generation
Exit plan mode and generate the final report using the synthesized findings.

---

Conduct an exhaustive sweep of the ENTIRE codebase to identify and remove AI-generated code slop. Use ultrathink extended thinking to thoroughly analyze every finding.

**Scope: Leave No Stone Unturned.**
- Scan EVERY source file in the repository — do not sample or spot-check.
- Compare patterns within each file AND across the codebase to identify inconsistencies.
- Consider the established conventions of each file/module when judging what is "slop."
- The goal is code that looks like a senior developer wrote it in one coherent session, not code that looks like it was generated piecemeal by an LLM.

**What Defines "AI Slop":**
Code that is technically correct but exhibits telltale signs of LLM generation: excessive verbosity, over-defensive programming, unnecessary abstractions, inconsistent style, and patterns that prioritize "safety" over readability and maintainability.

---

## PYTHON SLOP PATTERNS

**1. Unnecessary Defensive Checks:**
```python
# SLOP: Type already guarantees this
def process(data: dict[str, Any]) -> None:
    if data is None:
        return
    if not isinstance(data, dict):
        raise TypeError("Expected dict")
    # ... actual logic

# CLEAN: Trust the type signature
def process(data: dict[str, Any]) -> None:
    # ... actual logic
```

Flag ALL instances of:
- `if x is None` checks when type annotation doesn't include `None` / `Optional`
- `isinstance()` checks that duplicate what type hints already enforce
- Redundant truthiness checks: `if x is not None and len(x) > 0` when `if x:` suffices
- Try/except around operations that cannot raise in context (e.g., accessing a key you just set)

**2. Verbose Variable Declarations:**
```python
# SLOP: Variable used once immediately after
user_email = user.email
send_notification(user_email)

result = some_function()
return result

filtered_items = [x for x in items if x.active]
for item in filtered_items:
    process(item)

# CLEAN: Inline the expression
send_notification(user.email)

return some_function()

for item in items:
    if item.active:
        process(item)
```

Flag ALL instances of:
- Variables assigned and used exactly once on the very next line
- Variables that exist only to be immediately returned
- List comprehensions assigned to variables only to be immediately iterated
- Intermediate variables that don't aid readability or debugging

**3. Over-Commented Code:**
```python
# SLOP
# Initialize the user service
user_service = UserService()

# Get the user by ID
user = user_service.get_by_id(user_id)

# Check if user exists
if user is None:
    # Return 404 error
    raise NotFoundError("User not found")

# CLEAN: Code is self-documenting
user_service = UserService()
user = user_service.get_by_id(user_id)
if user is None:
    raise NotFoundError("User not found")
```

Flag ALL instances of:
- Comments that restate what the code does (e.g., `# Loop through items` above a for loop)
- Comments on every line or every few lines in simple code
- Comments that describe obvious operations (`# Import dependencies` above imports)
- Inconsistent comment density (heavily commented AI section vs. sparse human sections)
- Comments that don't match the established style of the file

**4. Unnecessary Exception Handling:**
```python
# SLOP: Catching exceptions that can't occur or shouldn't be caught here
try:
    user = users[user_id]  # Known to exist from prior validation
except KeyError:
    logger.error("User not found")
    return None

try:
    result = calculate_total(items)
except Exception as e:
    logger.error(f"Error calculating total: {e}")
    raise

# CLEAN
user = users[user_id]

result = calculate_total(items)  # Let exceptions propagate
```

Flag ALL instances of:
- Try/except wrapping code that cannot raise (accessing validated data)
- Bare `except:` or `except Exception:` that just logs and re-raises
- Try/except in internal functions called by code that already handles errors
- Exception handling inconsistent with the rest of the codebase

**5. Verbose String Formatting:**
```python
# SLOP
message = "User {} has {} items".format(user.name, len(items))
message = "User " + str(user.name) + " has " + str(len(items)) + " items"

# CLEAN (if codebase uses f-strings)
message = f"User {user.name} has {len(items)} items"
```

Flag ALL instances of:
- `.format()` or `%` formatting when codebase convention is f-strings
- String concatenation with `+` for simple interpolation
- Inconsistent string formatting style within the same file

**6. Redundant Truthiness Patterns:**
```python
# SLOP
if len(items) > 0:
if len(items) != 0:
if bool(value):
if value == True:
if value == False:
if value is not None and value != "":
return True if condition else False

# CLEAN
if items:
if items:
if value:
if value:
if not value:
if value:
return condition
```

Flag ALL instances of explicit length checks, bool() calls, comparisons to True/False, and ternaries that return booleans.

**7. Overly Verbose Dict/List Operations:**
```python
# SLOP
value = data.get("key") if data else None
value = data.get("key", None)  # None is already the default
items = list(items) if items else []

if key in data.keys():
for key in data.keys():
for i in range(len(items)):

# CLEAN
value = data.get("key") if data else None  # Only if data can be None
value = data.get("key")
items = list(items or [])

if key in data:
for key in data:
for i, item in enumerate(items):  # Or just: for item in items:
```

**8. Unnecessary Type Conversions:**
```python
# SLOP
str(f"Hello {name}")
list([x for x in items])
dict({k: v for k, v in items})
int(some_int)

# CLEAN
f"Hello {name}"
[x for x in items]
{k: v for k, v in items}
some_int
```

**9. Import Slop:**
```python
# SLOP: Unused imports, over-importing
from typing import Any, Dict, List, Optional, Union, Tuple, Callable  # Only using Optional
import os, sys, json  # sys and json unused

# SLOP: Inconsistent import style
from module import function1
from module import function2  # Should be combined

# SLOP: Importing then aliasing unnecessarily
from datetime import datetime as datetime
```

Flag ALL: unused imports, redundant imports, style inconsistent with file.

---

## REACT/TYPESCRIPT SLOP PATTERNS

**10. Unnecessary Null Guards:**
```typescript
// SLOP: Type guarantees user.profile exists
const name = user?.profile?.name ?? "";
const items = data?.items ?? [];

// When types are: { user: { profile: { name: string } } }
// CLEAN
const name = user.profile.name;
const items = data.items;
```

Flag ALL instances of:
- Optional chaining (`?.`) on properties that types guarantee exist
- Nullish coalescing (`??`) where the left side cannot be null/undefined
- Non-null assertions that indicate a type problem rather than solving one
- Redundant guards: `if (x !== null && x !== undefined)`

**11. Unnecessary Memoization:**
```typescript
// SLOP: Cheap operations don't need memoization
const fullName = useMemo(() => `${first} ${last}`, [first, last]);
const isActive = useMemo(() => status === 'active', [status]);
const doubled = useMemo(() => value * 2, [value]);

// SLOP: Stable references don't need useCallback
const handleClick = useCallback(() => setOpen(true), []);
const handleChange = useCallback((e) => setValue(e.target.value), []);

// SLOP: Empty dependency arrays on simple callbacks
const submit = useCallback(() => {
    onSubmit(formData);
}, []);  // Missing deps, or unnecessary useCallback

// CLEAN
const fullName = `${first} ${last}`;
const isActive = status === 'active';
const doubled = value * 2;

const handleClick = () => setOpen(true);
const handleChange = (e) => setValue(e.target.value);
```

Flag ALL instances of:
- `useMemo` for string concatenation, arithmetic, simple comparisons, object property access
- `useCallback` for callbacks that don't go to memoized children or effect deps
- `useCallback` with empty `[]` deps (either wrong or unnecessary)
- Memoization that doesn't match patterns used elsewhere in the codebase

**12. Verbose State Declarations:**
```typescript
// SLOP
const [isLoading, setIsLoading] = useState<boolean>(false);
const [items, setItems] = useState<Item[]>([]);
const [count, setCount] = useState<number>(0);

// CLEAN: Types are inferred
const [isLoading, setIsLoading] = useState(false);
const [items, setItems] = useState<Item[]>([]);  // Keep when inference wouldn't work
const [count, setCount] = useState(0);
```

Flag generic type parameters that TypeScript would infer correctly.

**13. Over-Defensive Props Handling:**
```typescript
// SLOP: Props types already define what's required
const Component = ({ items, onSelect }: Props) => {
    if (!items) return null;
    if (!onSelect) return null;
    if (!Array.isArray(items)) return null;

    // ...
};

// CLEAN: Trust your types
const Component = ({ items, onSelect }: Props) => {
    // ...
};
```

Flag runtime checks that duplicate TypeScript's compile-time guarantees.

**14. Unnecessary Fragment Wrappers:**
```typescript
// SLOP
return (
    <>
        <Component />
    </>
);

return (
    <React.Fragment>
        <div>Only child</div>
    </React.Fragment>
);

// CLEAN
return <Component />;
return <div>Only child</div>;
```

Flag fragments containing only a single child element.

**15. Verbose Event Handler Patterns:**
```typescript
// SLOP
onClick={(e) => handleClick(e)}
onChange={(e) => handleChange(e)}
onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}

// CLEAN
onClick={handleClick}
onChange={handleChange}
onSubmit={handleSubmit}  // With preventDefault in handleSubmit
```

Flag arrow functions that just pass through to another function.

**16. Type Assertion Abuse:**
```typescript
// SLOP: Casting to escape type errors
const data = response as any;
const user = data as unknown as User;
const items = (something as any).items as Item[];
// @ts-ignore
// @ts-expect-error

// SLOP: Unnecessary assertions
const element = document.getElementById("root") as HTMLElement as HTMLDivElement;
```

Flag ALL instances of: `as any`, `as unknown`, chained assertions, `@ts-ignore`, `@ts-expect-error`.

**17. Inconsistent Async Patterns:**
```typescript
// SLOP: Mixing patterns
async function loadData() {
    return await fetchData();  // Unnecessary await before return
}

// SLOP: .then() in async function
async function process() {
    fetchData().then(data => setData(data));
}

// CLEAN
async function loadData() {
    return fetchData();
}

async function process() {
    const data = await fetchData();
    setData(data);
}
```

**18. Verbose Conditional Rendering:**
```typescript
// SLOP
{condition ? <Component /> : null}
{condition ? <Component /> : <></>}
{condition === true && <Component />}
{!!condition && <Component />}  // When condition is already boolean

// CLEAN
{condition && <Component />}
```

**19. Unnecessary Spread Operations:**
```typescript
// SLOP
const newObj = { ...obj };  // Only to pass unchanged
const newArr = [...arr];     // Only to pass unchanged
<Component {...{ prop1, prop2 }} />

// When spreading just to spread
const combined = { ...defaults, ...overrides, ...{} };

// CLEAN
const newObj = obj;
const newArr = arr;
<Component prop1={prop1} prop2={prop2} />
```

Flag spreads that don't combine objects or that include empty objects.

**20. Effect Cleanup Slop:**
```typescript
// SLOP: Empty cleanup, unnecessary returns
useEffect(() => {
    doSomething();
    return () => {};  // Empty cleanup
}, []);

useEffect(() => {
    doSomething();
    return undefined;  // Explicit undefined
}, []);

useEffect(() => {
    const result = doSomething();
    return () => {
        // cleanup
    };
}, []);  // 'result' unused
```

---

## CROSS-LANGUAGE SLOP PATTERNS

**21. Comment Slop (Both Languages):**
Flag ALL instances of:
- `// TODO: implement` or `# TODO: implement` with no specifics
- Comments that restate function/variable names: `// Get user` above `getUser()`
- Commented-out code blocks
- JSDoc/docstrings that just repeat the function signature
- Section dividers: `// ========== HELPERS ==========`
- Comments inconsistent with the file's existing comment style/density

**22. Naming Inconsistencies:**
```python
# SLOP: Mixed conventions in same file
def getUserById():  # camelCase in Python
def get_user_by_email():  # snake_case

user_items = []  # snake_case
userCount = 0    # camelCase
```

```typescript
// SLOP: Mixed conventions
const user_name = "";    // snake_case in TS
const userEmail = "";    // camelCase
const UserAge = 0;       // PascalCase for variable
```

Flag ANY naming convention inconsistencies within a file.

**23. Dead Code Patterns:**
- Unreachable code after return/throw/break/continue
- Conditions that are always true or always false
- Unused function parameters (especially newly added AI parameters)
- Unused imports
- Variables assigned but never read
- Functions defined but never called

**24. Logging/Console Slop:**
```python
# SLOP: Excessive logging added "for debugging"
logger.info("Entering function process_data")
logger.debug(f"Processing {len(items)} items")
# ... one line of actual logic
logger.info("Exiting function process_data")
```

```typescript
// SLOP
console.log("Component mounted");
console.log("Props:", props);
console.log("State:", state);
```

Flag excessive logging/console statements inconsistent with rest of codebase.

**25. Error Message Slop:**
```python
# SLOP: Generic or over-verbose errors
raise ValueError("An error occurred while processing the data")
raise Exception("Something went wrong")
raise ValidationError(f"Validation error: The field 'email' with value '{email}' is not a valid email address format")

# CLEAN
raise ValueError(f"Invalid user_id: {user_id}")
raise ValidationError(f"Invalid email: {email}")
```

---

## OUTPUT FORMAT

**Part A — Codebase Scan Summary:**
```
Total Files Scanned: X
- Python files: X
- TypeScript/TSX files: X
- Other: X

Total Slop Instances Found: X
- Python: X instances across Y files
- React/TypeScript: X instances across Y files
```

**Part B — Findings by File:**
For each file with findings, report:
```
================================================================================
FILE: <path/to/file.py or .tsx>
SLOP DENSITY: <High | Medium | Low>
INSTANCES FOUND: X
================================================================================

Finding #<N>
Line(s): <line number(s)>
Category: <specific slop pattern name from above>
Current Code:
    <exact code snippet, max 10 lines>
Fixed Code:
    <exact replacement code>
Rationale: <brief explanation of why this is slop in context of this file>

---
<next finding>
```

**Part C — Pattern Summary:**
```
Most Common Slop Patterns:
1. <Pattern name>: X instances
   Files affected: <list>
2. <Pattern name>: X instances
   Files affected: <list>
...

Files Requiring Most Cleanup (ranked by slop density):
1. <file path>: X instances
2. <file path>: X instances
...

Codebase Style Conventions Detected:
- String formatting: <f-strings | .format() | mixed>
- Null handling: <optional chaining prevalent | explicit checks | mixed>
- Comment style: <sparse | moderate | heavy>
- Memoization approach: <conservative | liberal>
- Error handling: <let propagate | catch-and-rethrow | catch-and-log>
```

**Part D — Automated Fix Commands (if applicable):**
```
# Files that can be auto-fixed with tooling:
ruff check --fix <files>           # Python linting
eslint --fix <files>               # TS/React linting

# Manual review required:
<list of files needing human judgment>
```

**Part E — Recommendations:**
```
Patterns to Add to Linter Rules:
- <pattern>: <suggested eslint/ruff rule>

Style Guide Clarifications Needed:
- <ambiguous area where AI makes inconsistent choices>

Files That May Need Rewrite vs. Patch:
- <files where slop is so pervasive that targeted fixes would be more work than rewriting>
```

---

**Completeness Checklist:**
Before finalizing, verify:
- [ ] Every source file was scanned
- [ ] Every finding includes exact line numbers
- [ ] Every finding includes both current AND fixed code
- [ ] Patterns were compared against file-local conventions, not just global rules
- [ ] No false positives (legitimate patterns flagged as slop)
- [ ] Findings are actionable — someone could apply fixes without additional context
