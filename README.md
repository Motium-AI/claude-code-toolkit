# Namshub

**Code that must execute.**

Natural language in, verified deployed code out. The stop hook blocks completion until every checkpoint boolean passes — Claude cannot stop until the job is actually done.

## Invoke It (60 seconds)

```bash
git clone https://github.com/Motium-AI/namshub.git
cd namshub && ./scripts/install.sh
# Restart Claude Code, then:
```

```
> /build add a logout button to the navbar
```

Watch what happens:
1. 4 parallel Opus agents debate the approach (First Principles + AGI-Pilled + 2 dynamic)
2. Implements the plan
3. Runs linters, fixes all errors
4. Commits and pushes
5. Opens browser, verifies the button works
6. **Only then can it stop**

If step 5 fails, it loops back. You get working code, not promises.

## Four Skills

**`/build`** — Autonomous execution with 4-agent Lite Heavy planning. Give it a task, get verified deployed code.

**`/repair`** — Debugging loop. Auto-detects web vs mobile, collects logs, fixes, deploys, verifies. Loops until healthy.

**`/heavy`** — Multi-perspective analysis. 5 parallel Opus agents (2 required + 1 critical reviewer + 2 dynamic), structured disagreements, adversarial dialogue.

**`/burndown`** — Tech debt elimination. 3 detection agents scan for slop and architecture issues, prioritize by severity, fix iteratively until clean.

## The Stop Hook

When Claude tries to stop, the hook checks a deterministic boolean checkpoint:

```
is_job_complete: true?
linters_pass: true?
deployed: true?
web_testing_done: true?
what_remains: "none"?
```

All must pass. If not, Claude is blocked and must continue working.

## What This Is Not

- A replacement for your architectural judgment
- A guarantee of zero bugs (it verifies, but edge cases exist)
- Magic — it reads your files, runs your linters, and tests in your browser

## The Name

In Neal Stephenson's *Snow Crash*, a nam-shub is code that, once invoked, must execute to completion. That's what this toolkit enforces: Claude cannot stop until the job is done.

## Documentation

Full reference, hook system, and skill guides: [docs/index.md](docs/index.md)

## License

MIT — see [LICENSE](LICENSE)
