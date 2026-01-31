# Test Plan: Cross-Directory Auto-Approval Fix

## Summary of Fix

The fix adds `session_id` parameter to `_is_cwd_under_origin()` and related functions.
When session_id matches the state's session_id, the session is trusted regardless of directory.

## Files Modified

1. `config/hooks/_common.py` - Core fix in `_is_cwd_under_origin()` plus all calling functions
2. `config/hooks/pretooluse-auto-approve.py` - Passes session_id to function calls
3. `config/hooks/permissionrequest-auto-approve.py` - Passes session_id to function calls
4. `config/hooks/plan-mode-enforcer.py` - Passes session_id to function calls
5. `config/hooks/plan-mode-tracker.py` - Passes session_id to function calls
6. `config/hooks/deploy-enforcer.py` - Passes session_id to function calls

## Test Scenario 1: Verify cross-directory works with matching session

```bash
# Terminal 1: Start tmux session
tmux new-session -s test-fix

# Inside tmux, start appfix in project directory
cd /Users/olivierdebeufderijcker/Desktop/motium_github/claude-code-toolkit
/appfix

# Note the session_id from the state file
cat .claude/appfix-state.json | jq .session_id

# Claude should be in auto-approval mode - verify by making an edit
# It should NOT prompt for permission

# Now navigate Claude to a completely different directory
# Ask Claude to: "Navigate to /tmp and create a test file"

# If fix works: Edit should auto-approve (same session_id)
# If bug exists: Permission dialog will appear
```

## Test Scenario 2: Verify different sessions are still protected

```bash
# Terminal 1: Start appfix session A in project A
cd /path/to/projectA
/appfix
# Check session_id_A in .claude/appfix-state.json

# Terminal 2: Start NEW session in project B (different project)
cd /path/to/projectB
claude  # Regular claude, not appfix

# Project B should NOT get auto-approval from Project A's state
# because session_ids don't match
```

## Test Scenario 3: Headless verification

```bash
# Create a test script to simulate the hook input
cat > /tmp/test-hook.py << 'EOF'
import json
import sys
sys.path.insert(0, "/Users/olivierdebeufderijcker/Desktop/motium_github/claude-code-toolkit/config/hooks")
from _common import is_autonomous_mode_active, get_autonomous_state

# Simulate: cwd is in a different directory, but session_id matches
cwd = "/tmp"  # Different from origin_project
session_id = "3c457bb3-5940-4443-9fd4-e86e38700ad5"  # From current session

# With session_id (fix applied)
result_with_session = is_autonomous_mode_active(cwd, session_id)
print(f"With matching session_id: {result_with_session}")  # Should be True

# Without session_id (old behavior)
result_without_session = is_autonomous_mode_active(cwd, "")
print(f"Without session_id: {result_without_session}")  # Should be False

state, state_type = get_autonomous_state(cwd, session_id)
print(f"State type: {state_type}")  # Should be 'appfix'
EOF

python3 /tmp/test-hook.py
```

## Expected Results

1. **Test 1**: Auto-approval continues working when Claude navigates to /tmp
2. **Test 2**: Different sessions don't get cross-contaminated
3. **Test 3**: Script outputs:
   ```
   With matching session_id: True
   Without session_id: False
   State type: appfix
   ```

## Quick Verification (run now)

```bash
# Verify Python compiles
python3 -c "
import sys
sys.path.insert(0, '/Users/olivierdebeufderijcker/Desktop/motium_github/claude-code-toolkit/config/hooks')
from _common import is_autonomous_mode_active, get_autonomous_state, _is_cwd_under_origin
print('All imports successful')
print(f'is_autonomous_mode_active signature: cwd, session_id=\"\"')
print(f'_is_cwd_under_origin signature: cwd, user_state, session_id=\"\"')
"
```
