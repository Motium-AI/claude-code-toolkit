---
name: health
description: Report toolkit health metrics — memory system state, injection effectiveness, session diagnostics, trend analysis. Triggers on "/health", "system health", "how is memory doing", "check health".
---

# Health Report (/health)

Diagnose the toolkit's health — memory system, injection effectiveness, and session state.

## When to Use

- To check if the memory system is learning effectively
- To diagnose low citation rates or excessive demotions
- To review session health after a series of builds
- To verify the feedback loop is auto-tuning correctly

## Workflow

### Step 1: Gather Live Health Data

Run the health assessment against the current project:

```bash
cd {project_root} && python3 -c "
import sys, json; sys.path.insert(0, 'config/hooks')
from _health import generate_health_report
report = generate_health_report('$(pwd)')
print(json.dumps(report, indent=2))
"
```

### Step 2: Gather Historical Trends

Read recent health snapshots (archived by stop-validator on each successful stop):

```bash
cd {project_root} && python3 -c "
import sys, json; sys.path.insert(0, 'config/hooks')
from _health import get_health_history
history = get_health_history('$(pwd)', limit=5)
for h in history:
    ts = h.get('timestamp', '?')
    inj = h.get('injection', {})
    mem = h.get('memory', {})
    print(f'{ts}: events={mem.get(\"total_events\",0)} cited={inj.get(\"total_cited\",0)}/{inj.get(\"total_injected\",0)} rate={inj.get(\"citation_rate\",0):.1%}')
"
```

### Step 3: Diagnose and Report

Present findings as a structured Markdown report with these sections:

#### Memory Health
- Total events stored and breakdown by category
- Average event age and oldest event
- Recent cleanup activity

#### Injection Effectiveness (Feedback Loop)
- Citation rate (cited / injected) — target is 15%
- Number of demoted events (injected 2+ times, cited 0 times)
- Current MIN_SCORE (default vs auto-tuned)
- Score distribution of injected events

#### Session State
- Current mode (go/build/repair/none)
- Code changes detected this session
- Events injected at session start
- Events captured at last stop

#### Recommendations

Apply these rules to generate actionable recommendations:

| Condition | Recommendation |
|-----------|---------------|
| Citation rate < 10% | Memory events may lack relevance. Review search_terms quality in recent checkpoints. |
| Citation rate > 25% | System is learning well. Consider lowering MIN_SCORE to inject more. |
| Demoted events > 5 | Multiple events injected repeatedly without use. Consider pruning with `/compound` to capture better alternatives. |
| No events in 7+ days | No new memory events captured. System may not be learning from recent sessions. |
| MIN_SCORE drifting up (> 0.18) | Auto-tuner is being picky — citation rate is below target. Review if key_insight quality has degraded. |
| MIN_SCORE drifting down (< 0.08) | Auto-tuner is being generous — citation rate is above target. Memory is highly relevant. |
| Total events < 10 | Memory system is young. Keep using the toolkit — events accumulate automatically. |
| avg_age > 30 days | Most events are old. Fresh captures would improve relevance. |

### Step 4: Output Format

```markdown
## Toolkit Health Report

**Project**: {project_hash} | **Timestamp**: {now}

### Memory System
- **{total_events}** events ({by_category breakdown})
- Average age: **{avg_age}** days | Oldest: **{oldest}** days

### Injection Effectiveness
- Citation rate: **{rate}%** ({cited}/{injected}) — target 15%
- Demoted events: **{demoted}** | MIN_SCORE: **{min_score}** (tuned from {default})
- Score distribution: [{scores}]

### Session State
- Mode: **{mode}** | Code changes: {yes/no}
- Events injected: **{in}** | Events captured: **{out}**

### Recommendations
{bulleted recommendations from the table above}
```
