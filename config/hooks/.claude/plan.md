# Fix: Plan Auto-Approval Bug for Cross-Directory Sessions

## Bug Summary
When an appfix session navigates to a new directory (not under origin_project), auto-approval stops working because `_is_cwd_under_origin()` returns False.

## Root Cause
`_is_cwd_under_origin()` only checks if cwd is under origin_project. It doesn't consider that the SAME SESSION should be trusted regardless of directory.

## The Minimal Fix (3 changes in 1 file)

### File: `config/hooks/_common.py`

**Change 1**: Add `session_id` parameter to `_is_cwd_under_origin()` (lines 221-248)
- If session_id matches user_state's session_id, return True (trust same session)
- Otherwise fall back to existing directory check

**Change 2**: Add `session_id` parameter to functions that call `_is_cwd_under_origin()`:
- `is_appfix_active(cwd, session_id="")` - line 251
- `is_mobileappfix_active(cwd, session_id="")` - line 285
- `is_godo_active(cwd, session_id="")` - line 318
- `is_autonomous_mode_active(cwd, session_id="")` - line 352
- `get_autonomous_state(cwd, session_id="")` - line 451

**Change 3**: Update hook callers to pass session_id:
- `pretooluse-auto-approve.py` - extract session_id from input_data, pass to functions
- `permissionrequest-auto-approve.py` - same pattern

## Why This Is Safe
- Session matching is cryptographically strong (session IDs are unique)
- Only the same session can use its own state across directories
- Different sessions still get the directory check (safety preserved)

## Test Plan
1. Start appfix in project A
2. Navigate to unrelated directory /tmp/test-dir
3. Verify auto-approval still works (session_id matches)
4. Start new session in project B
5. Verify project A's state doesn't affect project B (session_id mismatch)
