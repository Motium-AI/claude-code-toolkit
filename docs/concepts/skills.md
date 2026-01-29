# Claude Code Skills: Domain-Specific Knowledge Injection

Reference documentation for configuring and using Claude Code skills—markdown files that inject domain expertise into Claude's context when relevant tasks are detected.

## Overview

Skills are markdown files that Claude Code automatically loads when it detects relevant tasks. Unlike hooks (which fire on lifecycle events), skills are **model-invoked**: Claude decides when to use them based on the task at hand.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Skill Invocation Flow                        │
├─────────────────────────────────────────────────────────────────┤
│  User Request → Claude analyzes task → Matches skill triggers   │
│       ↓                                                          │
│  Claude reads SKILL.md → Applies patterns → Executes task       │
└─────────────────────────────────────────────────────────────────┘
```

### Skills vs Hooks

| Aspect | Skills | Hooks |
|--------|--------|-------|
| Trigger | Model-invoked (task detection) | Lifecycle events (SessionStart, Stop) |
| Content | Domain knowledge, patterns, examples | Reminders, commands |
| Scope | Task-specific | Session-wide |
| Location | `~/.claude/skills/` (global) or `.claude/skills/` (project) | `~/.claude/settings.json` |

## Skill Locations

### Global Skills (All Projects)

```
~/.claude/skills/
├── nextjs-tanstack-stack/
│   └── SKILL.md
├── prompt-engineering-patterns/
│   └── SKILL.md
└── webapp-testing/
    └── SKILL.md
```

### Project Skills (Single Project)

```
<project-root>/
└── .claude/
    └── skills/
        └── project-specific-skill/
            └── SKILL.md
```

**Priority**: Project skills override global skills with the same name.

## Installing Skills

### Via Toolkit Installer (Recommended)

If you're using the Claude Code Toolkit:

```bash
cd prompts && ./scripts/install.sh
```

This script:
1. Backs up existing `~/.claude` configuration
2. Creates symlinks to toolkit commands, skills, and hooks
3. Configures settings.json with proper hook definitions

### Manual Installation

```bash
# Create skill directory
mkdir -p ~/.claude/skills/my-custom-skill

# Create SKILL.md
cat > ~/.claude/skills/my-custom-skill/SKILL.md << 'EOF'
---
name: my-custom-skill
description: Use when the user asks about [specific domain]...
---

# My Custom Skill

## When to Use This Skill
- Scenario 1
- Scenario 2

## Core Patterns
...
EOF
```

## SKILL.md Format

### Required Structure

```markdown
---
name: skill-name
description: Trigger description for Claude to match tasks against
---

# Skill Title

## When to Use This Skill
- Bullet points of applicable scenarios

## Core Patterns
[Domain-specific patterns with code examples]

## Best Practices
[Numbered guidelines]

## Common Pitfalls
[What to avoid]
```

### Trigger Description

The `description` field in frontmatter is critical—Claude uses it to decide when to invoke the skill:

```yaml
# Good: Specific triggers
description: Use when building Next.js applications with TanStack Table, implementing virtualized lists, or optimizing React performance with memoization.

# Bad: Too vague
description: Use for frontend development.
```

## Current Global Skills Registry

### 1. nextjs-tanstack-stack

**Location**: `~/.claude/skills/nextjs-tanstack-stack/`

**Triggers**: Next.js App Router, TanStack (Table, Query, Form, Virtual), Zustand, data tables, virtualization, memoization

**Coverage**:
- Server vs Client component patterns
- TanStack Query (factories, caching, mutations)
- TanStack Table with virtualization (10k+ rows)
- TanStack Form with Zod validation
- Zustand store patterns (slices, selectors)
- Performance optimization

**Structure**:
```
nextjs-tanstack-stack/
├── SKILL.md                              # Core patterns
├── references/
│   ├── tanstack-query-patterns.md
│   ├── tanstack-table-patterns.md
│   ├── tanstack-form-patterns.md
│   ├── zustand-patterns.md
│   ├── nextjs-app-router.md
│   └── performance-patterns.md
└── examples/
    ├── virtualized-data-table.tsx
    ├── query-with-error-boundary.tsx
    ├── form-with-validation.tsx
    └── zustand-query-sync.tsx
```

### 2. prompt-engineering-patterns

**Location**: `~/.claude/skills/prompt-engineering-patterns/`

**Source**: `@wshobson/agents/prompt-engineering-patterns`

**Triggers**: Prompt engineering, few-shot learning, chain-of-thought, prompt optimization

**Coverage**:
- Few-shot learning patterns
- Chain-of-thought prompting
- Prompt template libraries
- System prompt design
- Prompt optimization techniques

### 3. webapp-testing

**Location**: `~/.claude/skills/webapp-testing/`

**Source**: `@anthropics/skills/webapp-testing` (customized)

**Triggers**: Testing web applications, browser automation, Chrome debugging, console errors, authenticated apps

**Coverage**:
- **Chrome Integration (preferred)**: Real browser testing with `claude --chrome`
  - Tab management, navigation, element interaction
  - Console log debugging (`read_console_messages`)
  - Network request inspection (`read_network_requests`)
  - Authenticated app automation (Google Docs, Notion, etc.)
  - GIF recording for demos
- **Playwright Fallback**: For CI/CD and headless scenarios
  - Server lifecycle management (`with_server.py`)
  - Playwright sync API patterns
  - Reconnaissance-then-action pattern

**Structure**:
```
webapp-testing/
├── SKILL.md                      # Chrome-first, Playwright fallback
├── examples/
│   ├── chrome/                   # Chrome integration patterns
│   │   ├── form-testing.md
│   │   ├── console-debugging.md
│   │   └── authenticated-apps.md
│   └── playwright/               # Headless/CI patterns
│       └── *.py
└── scripts/
    └── with_server.py
```

### 4. async-python-patterns

**Location**: `~/.claude/skills/async-python-patterns/`

**Triggers**: Python asyncio, concurrent programming, async/await, I/O-bound applications

**Coverage**:
- 10 fundamental async patterns
- Producer-consumer, semaphores, context managers
- Real-world applications (web scraping, databases, WebSockets)
- Performance best practices

### 5. frontend-design

**Location**: `~/.claude/skills/frontend-design/`

**Triggers**: Building web components, pages, frontend interfaces

**Coverage**:
- Distinctive visual design (avoiding generic AI aesthetics)
- Typography, color, motion, spatial composition
- Design thinking before coding

### 6. ux-designer

**Location**: `~/.claude/skills/ux-designer/`

**Triggers**: User experience design, wireframes, accessibility

**Coverage**:
- User flow design
- Wireframe creation (ASCII or descriptions)
- WCAG 2.1 compliance checklists
- Design tokens
- Responsive behavior specs

### 7. godo

**Location**: `~/.claude/skills/godo/`

**Triggers**: /godo, "go do", "just do it", "execute this"

**Coverage**:
- Task-agnostic autonomous execution with completion checkpoint
- Mandatory plan mode before implementation
- Full fix-verify loop: implement → lint → commit → deploy → browser verify
- Cannot stop until checkpoint passes

**Guide**: [Godo Guide](../skills/godo-guide.md)

### 8. appfix

**Location**: `~/.claude/skills/appfix/`

**Triggers**: /appfix, "fix the app", "debug production", "check staging"

**Coverage**:
- Autonomous debugging with completion checkpoint (extends godo)
- Health check all services
- Collect logs (Azure Container Apps, browser console, LogFire)
- Diagnose → fix → commit → deploy → verify loop

**Guide**: [Appfix Guide](../skills/appfix-guide.md)

### 9. heavy

**Location**: `~/.claude/skills/heavy/`

**Triggers**: /heavy, "heavy analysis", "multiple perspectives", "debate this"

**Coverage**:
- Multi-perspective analysis with 6 parallel Opus agents
- 3 dynamic + 3 fixed perspectives (Critical Reviewer, Architecture Advisor, Shipping Engineer)
- Self-educating agents via codebase + web + vendor docs
- Structured disagreements and adversarial dialogue

### 10. deploy-pipeline

**Location**: `~/.claude/skills/deploy-pipeline/`

**Triggers**: /deploy, deployment questions, environment promotion

**Coverage**:
- Motium deployment pipeline guide (local → dev → test → prod)
- Azure Container Apps deployment
- GitHub Actions workflows
- Environment promotion strategy

### 11. mobileappfix

**Location**: `~/.claude/skills/mobileappfix/`

**Triggers**: Mobile app debugging, Maestro tests, React Native issues

**Coverage**:
- Mobile app debugging with Maestro E2E tests
- React Native / Expo diagnostics
- iOS and Android platform-specific debugging

### 12. skill-sandbox

**Location**: `~/.claude/skills/skill-sandbox/`

**Triggers**: /skill-sandbox, "test skill", "sandbox test"

**Coverage**:
- Test Claude Code skills in isolated tmux sandboxes
- Spawn multiple sessions, verify hook behavior
- Run integration tests for skills

### 13. toolkit

**Location**: `~/.claude/skills/toolkit/`

**Triggers**: /toolkit, "update toolkit", "toolkit status", "optimize CLAUDE.md"

**Coverage**:
- Toolkit management and information
- CLAUDE.md optimization and auditing
- Auto-update status and configuration

### 14. design-improver

**Location**: `~/.claude/skills/design-improver/`

**Triggers**: "improve design", "audit UI", "fix styling", "grade the interface"

**Coverage**:
- Recursively improve web UI design via vision-based screenshot analysis
- Design grading and targeted fix suggestions
- Iterative improvement loop

### 15. ux-improver

**Location**: `~/.claude/skills/ux-improver/`

**Triggers**: "improve UX", "fix usability", "audit user experience"

**Coverage**:
- Recursively improve web application UX via vision-based analysis
- User flow analysis and interaction audit
- Iterative usability improvement loop

### 16. docs-navigator

**Location**: `~/.claude/skills/docs-navigator/`

**Triggers**: "read the docs", "check documentation", unfamiliar codebase tasks

**Coverage**:
- Navigate project documentation efficiently
- Identify relevant docs before starting unfamiliar tasks
- Documentation discovery and orientation

### 17. revonc-eas-deploy

**Location**: `~/.claude/skills/revonc-eas-deploy/`

**Triggers**: /eas, "deploy to testflight", "push ota update", "build ios/android"

**Coverage**:
- RevOnc mobile app EAS deployment guide
- Build, deploy, and publish OTA updates via Expo Application Services
- iOS (TestFlight) and Android deployment workflows
- Build profiles and environment configuration

## Creating Custom Skills

### Step 1: Identify the Domain

Define clear boundaries:
- What tasks should trigger this skill?
- What patterns/knowledge does it provide?
- What does it NOT cover (delegate to other skills)?

### Step 2: Structure the SKILL.md

```markdown
---
name: my-domain-skill
description: Use when [specific triggers]. Triggers on [keywords].
---

# Domain Skill Title

## When to Use This Skill

**Use for:**
- Specific scenario 1
- Specific scenario 2

**Do NOT use for (delegate to):**
- Other scenario → other-skill

## Core Patterns

### Pattern 1: [Name]

[Explanation]

```language
[Code example]
```

### Pattern 2: [Name]
...

## Best Practices

1. First practice
2. Second practice
...

## Common Pitfalls

- Anti-pattern 1: Why it's bad and what to do instead
- Anti-pattern 2: ...

## Resources

- [Link to reference doc](references/topic.md)
- [Link to example](examples/example.tsx)
```

### Step 3: Add Reference Files (Optional)

For comprehensive skills, add supporting documentation:

```
my-domain-skill/
├── SKILL.md                    # Core patterns (entry point)
├── references/                 # Deep-dive documentation
│   ├── topic-1-patterns.md
│   └── topic-2-patterns.md
└── examples/                   # Working code examples
    └── complete-example.tsx
```

### Step 4: Test the Skill

1. Start a new Claude Code session
2. Ask a question that should trigger the skill
3. Verify Claude loads and applies the skill patterns
4. Refine trigger description if needed

## Skill Philosophy Alignment

Skills should align with the core development philosophy:

| Principle | Skill Implementation |
|-----------|---------------------|
| **Boring over clever** | Document explicit, obvious patterns |
| **Local over abstract** | Self-contained examples, not abstract theory |
| **Small composable units** | Break patterns into single-purpose sections |
| **Fail loud** | Include error handling patterns |
| **Tests as specification** | Include testing patterns where applicable |

## Integration with Hooks

Skills and hooks complement each other:

1. **SessionStart hook** reminds Claude to read project docs
2. **Skills** provide domain expertise for specific tasks
3. **Stop hook** reminds Claude to verify compliance

```
Session Start
     │
     ├── Hook: "Read CLAUDE.md, docs/index.md"
     │
     ├── User Request: "Build a data table"
     │       │
     │       └── Skill: nextjs-tanstack-stack activated
     │                  └── Applies TanStack Table patterns
     │
     └── Session End
             │
             └── Hook: "Verify CLAUDE.md compliance"
```

## Troubleshooting

### Skill Not Triggered

| Symptom | Cause | Fix |
|---------|-------|-----|
| Skill never activates | Vague description | Add specific trigger keywords |
| Wrong skill activates | Overlapping descriptions | Make descriptions more distinct |
| Skill partially applied | Too long/complex | Split into focused skills |

### Skill Conflicts

If multiple skills could apply:
1. Claude will choose the most specific match
2. Project skills override global skills
3. Consider merging overlapping skills

## Related Documentation

- [Claude Code Hooks](./hooks.md) - Lifecycle event handlers
- [Commands Reference](./commands.md) - Custom slash commands
- [Config Files](../../config/) - Actual hook/skill/command files for installation
- [CLAUDE.md Standards](../philosophy.md) - Core philosophy
- [Official Skills Documentation](https://docs.anthropic.com/en/docs/claude-code/skills) - Anthropic reference
