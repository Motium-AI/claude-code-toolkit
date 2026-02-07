# Parallel Agent Isolation (Git Worktrees)

When running multiple agents in parallel, each agent should use its own **git worktree** to avoid conflicts on git operations, checkpoint files, and version tracking.

## Why Worktrees?

Without isolation, parallel agents cause:
- Race conditions on `git commit`/`git push`
- Checkpoint invalidation chaos (Agent A's version invalidated by Agent B's commit)
- Silent merge conflicts when editing same files

## Worktree Workflow

```
COORDINATOR (main repo)
├── Creates worktrees for each agent
├── Each agent diagnoses/fixes independently
├── Sequential merge after completion
└── Single deployment after merge

AGENT WORKTREE
├── Own branch: claude-agent/{agent-id}
├── Own .claude/ directory (checkpoint, state)
├── Independent log collection
└── Independent version tracking
```

## Creating a Worktree

```bash
python3 ~/.claude/hooks/worktree-manager.py create <agent-id>
# Returns: /tmp/claude-worktrees/<agent-id>
```

## Merging Agent Work

```bash
python3 ~/.claude/hooks/worktree-manager.py merge <agent-id>
# If conflict (exit code 2): fall back to sequential execution
python3 ~/.claude/hooks/worktree-manager.py cleanup <agent-id>
```

## Coordinator Deploy Pattern

**ONLY the coordinator deploys. Subagents NEVER deploy.**

```
1. Create worktrees for each agent
2. Spawn Tasks (each gets worktree path in prompt)
3. Wait for all Tasks
4. Sequential merge (abort on conflict → fall back to sequential)
5. SINGLE deploy (coordinator only): git push && gh workflow run && gh run watch
6. Cleanup worktrees
```

**SUBAGENT RULES (enforced by state file):**
- If `coordinator: false`, NEVER run `gh workflow run` or `git push`
- Commit locally in worktree only
- Mark `needs_deploy: true` in checkpoint

**Coordination detection:**
- Skills set `coordinator: false`, `parallel_mode: true` in worktree `autonomous-state.json`
- `deploy-enforcer.py` blocks subagent deploy attempts

## Garbage Collection

```bash
python3 ~/.claude/hooks/worktree-manager.py gc           # Default 8-hour TTL
python3 ~/.claude/hooks/worktree-manager.py gc --dry-run # Preview cleanup
```
