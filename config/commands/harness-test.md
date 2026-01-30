---
description: Test harness changes in isolated sandbox
argument-hint: [--test <name>] [--interactive] [--keep-sandbox]
---

# /harness-test

Test changes to Claude Code hooks, skills, and settings in an isolated sandbox before committing.

## Arguments

- `--test <name>` - Run a specific test case
- `--interactive` - Open tmux for manual observation
- `--keep-sandbox` - Don't destroy sandbox after tests
- `--all` - Run all test cases, not just relevant ones

## Instructions

1. **Read the harness-test skill**:
   @~/.claude/skills/harness-test/SKILL.md

2. **Execute the workflow**:
   Follow the phases in the skill document:
   - Phase 1: Detect harness project and changes
   - Phase 2: Setup sandbox with modified hooks
   - Phase 3: Propagate uncommitted changes
   - Phase 4: Run test cases
   - Phase 5: Report results and cleanup

3. **Handle results**:
   - If all tests pass, report success
   - If tests fail, report which tests failed and why
   - Write results to `.claude/harness-test-state.json`
