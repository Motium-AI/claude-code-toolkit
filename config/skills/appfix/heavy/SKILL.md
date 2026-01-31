# Heavy Debugging Analysis (/repair)

This skill file defines the 3-agent Lite Heavy planning phase for `/repair` debugging.

## 3 Agent Structure for Debugging

| Agent | Purpose |
|-------|---------|
| **Research Agent** | Root cause analysis - analyze logs, formulate hypotheses, test them |
| **First Principles** | Simplification lens - what's the minimal fix? What can be deleted? |
| **Dynamic Perspective** | One domain expert (Security, Data Flow, Error Handling, etc.) |

## Why 3 Agents (Not 4) for Debugging

- **No AGI-Pilled**: Debugging is grounded in reality, not aspirational. We're fixing what's broken, not reimagining architecture.
- **Research focus**: Root cause analysis is the critical path for debugging - one dedicated research agent.
- **Single dynamic**: One specialized perspective catches what Research and First Principles miss, without overloading.

## Agent Templates

### AGENT 1: Research Agent (Root Cause Analysis)

```
Task(
  subagent_type="general-purpose",
  description="Research Agent: Root cause analysis",
  model="opus",
  prompt="""You are a debugging research agent focused on root cause analysis.

Your job:
1. Analyze available evidence: logs, error messages, stack traces, browser console
2. Formulate 3-5 hypotheses about the root cause
3. For each hypothesis, define what evidence would confirm or refute it
4. Rank hypotheses by likelihood based on available evidence

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

Use your tools to:
- Read log files, trace outputs
- Search codebase for error patterns, recent changes
- Check git history for recent commits that might have caused the issue
- Look for similar issues in the codebase or documentation

Output: A ranked list of hypotheses with supporting evidence and next steps to validate.
"""
)
```

### AGENT 2: First Principles Analysis

```
Task(
  subagent_type="general-purpose",
  description="First Principles Analysis",
  model="opus",
  prompt="""You apply the Elon Musk algorithm to this bug fix:

1. **Question the requirement** - Is this actually a bug, or a misunderstanding?
2. **Delete** - What code can be removed rather than fixed?
3. **Simplify** - What's the minimal fix that solves the problem?
4. **Accelerate** - Only after simplifying, optimize

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

For this specific bug:
- What's the simplest possible fix?
- Is there code we can delete instead of fixing?
- Are we fixing a symptom or the actual root cause?
- What's the minimal change to restore correct behavior?

Use your tools to explore the codebase and understand what exists.

Output: The simplest possible fix, with rationale for why more complex approaches are unnecessary.
"""
)
```

### AGENT 3: Dynamic Perspective (Choose Based on Bug Type)

Choose ONE of these based on the bug type:

#### Option A: Security Engineer (for auth/permissions bugs)
```
Task(
  subagent_type="general-purpose",
  description="Security Engineer perspective",
  model="opus",
  prompt="""You are a security engineer reviewing this bug fix.

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

Analyze:
- Could this bug be exploited?
- Does the fix introduce new security risks?
- Are there related security issues we should check?
- What validation/sanitization might be missing?

Use your tools to search for related security patterns in the codebase.
"""
)
```

#### Option B: Data Flow Analyst (for data/state bugs)
```
Task(
  subagent_type="general-purpose",
  description="Data Flow Analysis perspective",
  model="opus",
  prompt="""You trace data flow to find the bug.

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

Trace:
1. Where does the data enter the system?
2. What transformations happen?
3. Where does it diverge from expected behavior?
4. What state mutations might cause this?

Use your tools to trace the data path through the codebase.
"""
)
```

#### Option C: Error Handling Expert (for crash/exception bugs)
```
Task(
  subagent_type="general-purpose",
  description="Error Handling Expert perspective",
  model="opus",
  prompt="""You specialize in error handling and recovery.

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

Analyze:
- What error conditions aren't being handled?
- What exceptions might be unhandled?
- Are there race conditions or timing issues?
- What edge cases might trigger this?

Use your tools to find error handling patterns and gaps.
"""
)
```

#### Option D: Integration Specialist (for API/network bugs)
```
Task(
  subagent_type="general-purpose",
  description="Integration Specialist perspective",
  model="opus",
  prompt="""You specialize in system integration and API issues.

Bug/Issue description: [DESCRIBE THE BUG/FAILURE]

Analyze:
- What API contracts might be violated?
- Are there timing/ordering issues between services?
- What network conditions might cause this?
- Are there version mismatches or schema changes?

Use your tools to check API definitions, network calls, and service interactions.
"""
)
```

## Execution Flow

1. **Read this file** (`~/.claude/skills/appfix/heavy/SKILL.md`)
2. **Launch all 3 agents in parallel** (single message, 3 Task calls)
3. **Wait for all agents to complete**
4. **Synthesize findings** into your debugging plan
5. **Call ExitPlanMode** with the plan

## Keywords for Agent Detection

The `lite-heavy-tracker.py` hook detects agents by description keywords:

| Agent Type | Keywords in Description |
|------------|------------------------|
| Research | "research", "root cause", "hypothesis", "investigate" |
| First Principles | "first principles", "first-principles" |
| Dynamic | "perspective", "analysis", "review", "expert" |

Make sure your Task descriptions include these keywords!
