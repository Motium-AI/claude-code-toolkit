Integrating Compound Engineering and Supermemory into the Namshub Agent Harness

This research was conducted on January 30th, 2026, using heavy multi-perspective analysis with twelve Opus agents across four rounds. Two repositories were analyzed -- compound-engineering-plugin with six thousand two hundred stars, and claude-supermemory.



Executive Summary

Two open-source projects solve the same fundamental problem -- Claude Code sessions don't learn from each other. Each session starts from scratch, rediscovering problems that previous sessions already solved.

The git history of this toolkit proves the cost. Thirteen incremental commits discovering auto-approval edge cases one by one. And a four hundred seventy-three line PID-scoping feature built with high confidence, then entirely deleted twenty-five minutes later -- with no record of why it failed.

The integration opportunity is real but narrower than it appears. After five parallel Opus agents, an adversarial dialogue, and red-team stress testing, the analysis converged on a local-first approach. About three hundred forty lines of new code across five files. No cloud dependencies. No npm packages.

From compound-engineering's twenty-eight agents, twenty-four commands, and fifteen skills, we need exactly one technique -- the Compound step for structured knowledge capture. From supermemory's four hooks and cloud API, we need the concept of cross-session memory injection, but implemented locally.



Source Repository Analysis

First, compound-engineering-plugin by Every Inc. Six thousand two hundred stars, four hundred ninety-two forks, one hundred fifty-three commits.

It's a Claude Code plugin marketplace implementing a complete software development methodology. AI agents handle planning, implementation, review, and knowledge capture in a self-improving loop.

The core philosophy -- each unit of engineering work should make subsequent units easier, not harder. Traditional development accumulates technical debt. Compound engineering inverts this by creating a compounding knowledge loop where learnings from each cycle feed into the next.

The architecture includes twenty-eight agents as markdown files with YAML frontmatter. Twenty-four slash commands -- five core workflow plus nineteen utility. Fifteen skills as directories with skill markdown plus optional references and scripts. One MCP server -- Context7. Zero hooks.



The Four-Step Loop

The workflow has four steps. Plan, work, review, compound.

Step one, plan. Transform feature descriptions into detailed implementation plans. AI agents research the codebase, external docs, and institutional learnings.

Step two, work. Execute the plan systematically. Create a branch or worktree, break the plan into tasks, implement, test, commit, create a pull request.

Step three, review. Multi-agent code review using thirteen-plus parallel agents. Security, performance, architecture, patterns, simplicity, and more. Findings are categorized by severity -- P1, P2, P3.

Step four, compound. Document the recently solved problem. Parallel sub-agents extract problem context, solution, prevention strategies, cross-references, and category. Then write a structured markdown file to docs/solutions.



Key Techniques from Compound Engineering

Institutional knowledge capture. The Compound step writes structured learnings to docs/solutions with YAML frontmatter. Fields include problem type, module, symptoms, root cause, severity, and tags. A learnings-researcher agent searches these before new work begins.

Massive parallelism. The review workflow launches thirteen-plus review agents simultaneously. The deepen-plan command spawns forty-plus parallel agents.

Agent-native architecture philosophy. Parity means agents can do anything users can. Granularity means atomic primitives. Composability means new features equal new prompts. Emergent capability follows naturally.

Specialized review personas like DHH Rails reviewer, security sentinel, and performance oracle.

Dynamic skill discovery. Commands dynamically find all installed skills and spawn sub-agents per relevant skill.

Cross-platform CLI. Bun and TypeScript CLI converts Claude Code plugins to OpenCode and Codex formats.



Second Repository -- Claude Supermemory

By Supermemory AI. Sixty-six stars, three forks. It's a Claude Code plugin that gives Claude persistent memory across sessions using the Supermemory cloud API. Built by Supermemory, founded by Dhravya Shah, which positions itself as a Universal Memory API for AI apps.

The architecture has four hooks as Node.js CommonJS bundles -- esbuild compiled, self-contained, about two hundred kilobytes each. One skill for super-search. Two commands for indexing and logout. MCP server is configured but disabled -- uses direct SDK instead.



Hook Lifecycle in Supermemory

Session start runs context-hook. Calls the Supermemory profile API. Returns static facts for persistent preferences and dynamic facts for recent context. Injects as a supermemory-context block via additional context.

User prompt submit runs prompt-hook. Currently a no-op stub.

Post tool use runs observation-hook. Currently a no-op stub, triggered for Edit, Write, Bash, and Task.

Stop runs summary-hook. Reads the JSONL transcript, formats user and assistant messages plus tool use, strips system reminders, and sends to the Supermemory add API with a project-scoped container tag.



Key Techniques from Supermemory

Project-scoped memory isolation. Container tag from SHA-256 of git root path.

Auto-maintained user profile. Static facts for persistent preferences plus dynamic facts for recent context, evolving automatically.

Semantic search plus hybrid retrieval. Vector plus keyword search with similarity scores.

Transcript compression. Tool observations compressed to one-line summaries. Edit becomes edited file.py, old to new. Read tool results are skipped entirely.

Incremental capture. Tracks last captured UUID per session, only sends new content.

Content sanitization. Strips system-reminder and supermemory-context tags to prevent recursive injection.

Authentication via environment variable, credentials file, or browser-based OAuth flow on local port nineteen-eight-seven-six.



Comparison to CLAUDE.md

Storage -- CLAUDE.md uses local markdown files, supermemory uses cloud API.

Update mechanism -- CLAUDE.md requires manual editing, supermemory captures automatically on session stop.

Retrieval -- CLAUDE.md injects the full file every session, supermemory uses semantic search to select a relevant subset.

Cross-session learning -- CLAUDE.md has none since it's the same content every time, supermemory evolves automatically.

Cost -- CLAUDE.md is free, supermemory requires an API subscription.

Privacy -- CLAUDE.md is fully local, supermemory sends data to the cloud.



What Each Repository Contributes

From compound-engineering-plugin.

Plan step with research and write plan -- Namshub already has this via plan-mode-enforcer and build phase zero-point-five. No integration needed.

Work step for execute and commit -- Namshub already has via build phases one and two. No integration needed.

Review step with thirteen-plus parallel agents -- Namshub already has via heavy with five agents plus dialogue. No integration needed.

Compound step for capturing learnings -- this is the gap. Yes, integrate.

Docs/solutions knowledge base -- this is the gap. MEMORIES.md has two entries for one hundred thirty-seven commits. Yes, integrate.

Learnings-researcher for grep before planning -- this is the gap. Build doesn't search past solutions. Yes, integrate.

Git worktree integration, file-based YAML todo tracking, Context7 MCP, dynamic skill discovery, twenty-eight specialized agents, auto-approval during autonomous mode, deepen-plan with forty-plus agents -- all either already exist or aren't needed.



From claude-supermemory.

Session start context injection -- Namshub partially has via read-docs-reminder which injects static docs. Take the concept only.

Auto-maintained user profile -- no, requires cloud dependency.

Semantic search plus hybrid retrieval -- no, requires cloud dependency.

Transcript capture at stop -- no, data exfiltration risk.

Project-scoped memory isolation -- Namshub already has via .claude state files. No integration needed.

Content sanitization pattern -- yes, borrow this pattern.

Incremental UUID tracking -- not needed for local files.



Recommended Approach

Build three components totaling about three hundred forty lines.

Component one -- the compound skill. About one hundred seventy-five lines across skill markdown and references. Captures solved problems as structured markdown with YAML frontmatter.

Component two -- learnings lookup. About seven lines editing the build skill. Greps docs/solutions before planning in phase zero-point-five.

Component three -- context injection. About one hundred fifty lines for the hook and settings edit. Injects recent and relevant solutions at session start.



How Knowledge Compounds

Session A solves an auth bug. User runs /compound. This writes a solution file to docs/solutions/runtime-errors with a date stamp.

Session B starts. The compound-context-loader hook injects a note -- one past solution matching recent commits.

Session B runs /build. Phase zero-point-five greps docs/solutions. Finds the auth solution.

Session B avoids rediscovering the auth bug. Saves ten to thirty minutes.

Session B solves a different problem. /compound captures it.

Each session makes the next session smarter.



Why Not Supermemory Cloud Integration

The Critical Reviewer identified ten implementation risks. Here are the top three.

Risk one -- stop hook race condition. High severity. Namshub's stop-validator blocks sessions via exit code two. Supermemory's summary-hook runs in parallel and uploads transcripts even on blocked stops. This creates duplicate memory entries -- two to four times per autonomous session.

Risk two -- sensitive code exfiltration. High severity. The transcript-formatter includes file edits, bash commands, and tool results with only two hundred to five hundred character truncation and zero secret filtering. Every git diff, psql output, and env read gets sent to a third-party cloud API.

Risk three -- thirty-second session start timeout. High severity. The context-hook makes a network call to the Supermemory API on every session start. The October 2025 incident report documents a twenty-eight minute degradation with cascading retry amplification. During such periods, every session start takes the full thirty-second timeout.

The local approach captures eighty percent of the value at five percent of the complexity, with zero operational risk.



Tradeoff One -- Where Do Solution Files Live

Option one -- target project at project/docs/solutions. Project-specific, version-controlled with the code, PR-reviewable. Downside is no cross-project learning -- every project starts cold.

Option two -- toolkit repo at namshub/docs/solutions. Shared across all projects, auto-updated. Downside is merge conflicts between developers and unrelated solutions polluting context.

Option three -- user-level at ~/.claude/solutions. Cross-project, no git noise. Downside is not version-controlled and not shareable.

Recommendation -- target project. Cross-project learning is a phase two optimization. The immediate value is preventing the same project from rediscovering its own problems.



Tradeoff Two -- Automatic vs Manual Triggering

Option one -- manual via /compound. User controls what gets captured, no noise. Downside is the knowledge base never populates.

Option two -- automatic via stop hook prompts capture. Knowledge accumulates without effort. Downside is trivial fixes get captured, creating noise.

Option three -- semi-automatic, integrated into build phase three. Captures during autonomous execution. Downside is it only works for build sessions, not ad-hoc fixes.

Recommendation -- start manual with /compound, add a prompt in build phase three saying if the fix was non-trivial, run /compound to capture this learning. Human in the loop for quality control.



Tradeoff Three -- Retrieval Strategy

Option one -- grep over YAML frontmatter. Zero infrastructure, fast, deterministic. Downside is no stemming -- auth won't match authentication -- and no semantic matching.

Option two -- LLM keyword expansion plus grep. Handles synonyms, Claude reads and semantically matches. Downside is non-deterministic and may be skipped under context pressure.

Option three -- local embeddings. True semantic search, handles novel queries. Downside is new dependency, setup complexity, overkill for under two hundred files.

Recommendation -- grep for the hook since it's deterministic and fast. LLM-mediated search in build phase zero-point-five where Claude reads matching files and reasons about relevance. Two-tier approach matching Namshub's existing pattern -- hooks do mechanical work, skills do intelligent work.



Blocking Issues

Issue one -- grep regex bug. Blocking. The proposed pattern using bracket keyword bracket treats the keyword as a regex character class, matching any file containing any single letter from the keyword. Every query returns every file.

Testing shows that searching for tags with auth in brackets matches a line with tags database, caching, redis because A is in database.

Fix -- use grep -riwl keyword docs/solutions for word-match files-only in the hook, and grep -ri with word boundary backslash-b for tag-specific searches.

Issue two -- no auto-trigger for /compound. Blocking. Without automatic triggering, the knowledge base depends on the user remembering to type /compound. It won't populate.

Fix -- add a line to build's phase three -- if the task required debugging or non-trivial investigation, capture the learning with /compound. Also add to the stop-validator's checklist prompt.

Issue three -- session start injects recent, not relevant. Medium severity. The hook injects the five most recent solutions regardless of current task. If you fixed CSS yesterday and are debugging auth today, the CSS solution wastes context tokens.

Fix -- the hook extracts keywords from recent git commit subjects as a proxy for current work area and greps for matching solutions alongside recent ones. The implementation includes both get-recent-solutions and grep-solutions with get-git-keywords.



Concrete Implementation

File one -- /compound skill at config/skills/compound/SKILL.md.

The skill captures solved problems as structured markdown. Workflow has five steps. Extract context from the current session -- problem, investigation, root cause, solution, prevention. Classify with YAML frontmatter against a defined schema -- problem type, component, root cause, resolution type, severity, symptoms, tags. Determine file path as docs/solutions/category/slug-date.md. Write the document with structured sections -- problem, symptoms, what didn't work, root cause, solution, why this works, prevention, related. Confirm with path and tags for searchability.

Triggers are /compound, document this solution, and capture this learning.



File two -- YAML schema reference at config/skills/compound/references/solution-schema.md.

Defines the controlled vocabulary.

Eleven problem types mapped to category directories -- build error, test failure, runtime error, performance issue, config error, dependency issue, integration issue, logic error, design flaw, infrastructure issue, security issue.

Sixteen root causes -- missing config, wrong API usage, race condition, state management, missing validation, missing dependency, wrong assumption, incomplete migration, environment mismatch, logic error, type error, schema mismatch, memory issue, timeout, permission error, platform difference.

Ten resolution types -- code fix, config change, dependency update, architecture change, test fix, environment fix, workaround, documentation, rollback, deletion.

Four severity levels -- critical, high, medium, low.



File three -- context injection hook at config/hooks/compound-context-loader.py.

Session start hook, about one hundred forty lines. Finds docs/solutions in the project directory. Gets five most recent solutions by modification time. Extracts keywords from recent git commit subjects. Greps for keyword-matched solutions, maximum three. Outputs a concise summary -- total count, recent list with tags, keyword-matched list.

Registered in settings.json after read-docs-reminder with five-second timeout.



File four -- build skill modification at config/skills/build/SKILL.md.

Adds about seven lines to phase zero-point-five step two, explore the codebase first.

If docs/solutions exists, grep -r -l -i for task-relevant keywords in docs/solutions. Read any matching files. They contain root causes, failed attempts, and prevention guidance from previous sessions.



File five -- settings registration at config/settings.json.

Adds the new hook to both session start groups, default and compact matcher.

Type is command. Command runs python3 with the hook path. Timeout is five seconds.



Example Solution Document

Based on the real PID-scoping failure in this repo's history.

YAML frontmatter -- title is macOS basename breaks PID-scoped state file paths. Date is January 30th 2026. Problem type is runtime error. Component is hooks common.py get-ancestor-pid function. Root cause is platform difference. Resolution type is deletion. Severity is high.

Symptoms list -- PID-scoped state files not found on macOS, auto-approval hooks fail silently, works on Linux but fails on macOS.

Tags -- hooks, macos, pid, basename, platform, state-files.

Problem section -- PID-scoped state isolation silently failed on macOS because get-ancestor-pid used basename on proc-style paths that don't exist on macOS.

What didn't work section -- attempt one added fallback path for proc not existing. Failed because the basename call itself was the problem, not the path lookup. Attempt two used psutil for cross-platform process info. Failed because it violated the no new dependencies constraint.

Root cause section -- ps -o comm= returns different formats on Linux versus macOS. Linux returns the full path like /usr/bin/python3. macOS returns the name only like python3. Calling basename on a name without path separators strips incorrectly.

Solution section -- entire PID-scoping approach was deleted, four hundred seventy-three lines. Replaced with simpler session-id-based isolation via git worktrees.

Prevention section -- process inspection APIs behave differently across platforms. Test hooks on both macOS and Linux before merging. Prefer session-id isolation over PID-based isolation.



Risk Mitigations

Risk one -- YAML schema drift with inconsistent tags. Mitigation -- schema reference file with controlled vocabulary. The compound skill validates against it.

Risk two -- stale solutions misleading Claude. Mitigation -- add obsolete true to frontmatter. Hook filters out obsolete entries. Periodic review via /burndown.

Risk three -- git noise from solution files. Mitigation -- solutions in target project's docs/solutions are included in PRs and reviewed by the team. Feature, not bug.

Risk four -- context poisoning from bad captures. Mitigation -- human in the loop. Only /compound which is manual trigger writes solutions. No automatic capture.

Risk five -- grep degrades past about two hundred files. Mitigation -- acceptable for now. At that scale, add local embeddings or LLM-powered summarization. YAML frontmatter structure makes future migration straightforward.

Risk six -- memory poisoning attacks. Mitigation -- local files version-controlled in git are auditable via git log. No cloud attack surface.



Future Phases

Phase two -- auto-prompt for /compound in stop-validator checklist. After phase one proves the knowledge base has value.

Phase three -- cross-project solution sharing via symlinked shared docs/solutions. When two or more projects accumulate twenty-plus solutions each.

Phase four -- local embeddings for semantic search over solutions. When solutions exceed about two hundred files and grep quality degrades.

Phase five -- supermemory cloud integration for team-wide memory. When cloud reliability and data sensitivity concerns are resolved.



Multi-Agent Analysis Details

This report used /heavy multi-perspective analysis.

Research round had two agents -- compound-engineering researcher and supermemory researcher. Deep-read both repos plus web context.

Round one had five agents -- first principles, AGI-pilled (which failed with API encoding error), plugin architecture, context engineering, and critical reviewer. Parallel analysis from five perspectives.

Round one-point-five had two agents -- first principles defender and context engineering challenger. Adversarial dialogue on key tradeoff.

Round two had two agents -- deep-dive implementation and red-team stress test. Concrete implementation plus risk analysis.

The user stated they were not looking for contrarian takes, this is a massive opportunity and we need to integrate it. All agents accepted the integration goal and debated how, not whether.



Key Consensus from Three or More Agents

The Compound step is the number one integration target. Every agent identified institutional knowledge capture as the highest-value technique. Namshub has zero mechanism for this today.

Compound-engineering should stay as a plugin, supermemory needs local reimplementation. Plugin architecture showed zero hook conflicts for compound-engineering since it has no hooks. Supermemory collides on four of four hook events.

The stop hook race condition is dangerous. Namshub's stop-validator with exit code two blocking runs in parallel with supermemory's thirty-second summary hook, creating premature transcript uploads.

Sensitive code exfiltration to supermemory's cloud API is a top risk. Transcript-formatter includes file edits, bash commands, and tool results with only two hundred to five hundred character truncation and zero secret filtering.



Adversarial Dialogue Outcome

Contested point -- integration scope. Minimal local-only at about three hundred ten lines versus full cloud-integrated using a five-phase four buckets architecture.

First principles argued -- grep over local YAML gives eighty percent of semantic search value. The project's own research report warns against complex memory systems. The LLM itself is the semantic search engine. No cloud dependency needed.

Context engineering argued -- most agent failures are context failures. The tiered retrieval protocol with static, semantic, grep, and on-demand ensures right context at right time. Local grep cannot do semantic similarity matching.

Resolution -- context engineering conceded the architecture but proved the problem.

Key evidence -- thirteen commits on auto-approval subsystem, each session discovering one new edge case. Four hundred seventy-three lines of PID-scoping built and destroyed with no record of why it failed. Two-entry MEMORIES.md for a one hundred thirty-seven commit project.

Context engineering's concession -- I was proposing a cathedral when a well-placed bridge would suffice.

First principles' concession -- cross-session knowledge loss is real and measured, not theoretical.

Persistent disagreement -- whether grep degrades past about two hundred solution files. First principles says grep plus LLM keyword expansion is sufficient indefinitely. Context engineering says semantic search will be needed at scale. Deferred to phase four -- measure before optimizing.



Critical Reviewer Top Ten Risks

Risk one -- stop hook race with premature transcript upload. High severity. Avoided by not integrating supermemory.

Risk two -- thirty-second session start network call on every session. High severity. Avoided by local-only approach.

Risk three -- context window inflation from concatenated additional context. Medium-high severity. Mitigated by compact hook output at about four hundred tokens.

Risk four -- known Claude Code bug with double hook execution. Medium severity. Mitigated by no plugin hooks, settings.json only.

Risk five -- sensitive code uploaded to cloud API. High severity. Avoided by no cloud integration.

Risk six -- two runtime dependencies with Python plus Node.js. Medium severity. Avoided by Python only.

Risk seven -- no state coordination between Namshub and supermemory. Medium severity. Avoided by single system.

Risk eight -- auth flow breaks in headless or CI environments. Medium severity. Avoided by no auth needed.

Risk nine -- subagent explosion from compound-engineering review. Medium severity. Mitigated by compound installed as plugin, not extracted.

Risk ten -- commercial lock-in with no exit strategy. Medium severity. Avoided by local files with no vendor.



Plugin Architecture Analysis

Compound-engineering as plugin is recommended. Zero hooks means no composition risk. One skill name collision with frontend-design is resolved by plugin namespacing. Zero command collisions since it uses workflows prefix. Context7 MCP adds value without conflict. Installation uses plugin marketplace add then plugin install compound-engineering.

Supermemory extracted into Namshub was considered but rejected. Would require copying six CommonJS scripts into config/hooks/supermemory. Would require rewriting plugin root references. Would add Node.js runtime dependency alongside Python. Would require manual upstream update tracking. Rejected in favor of local-only reimplementation.



Context Engineering Four Buckets Assessment

Bucket one, write. Current Namshub has MEMORIES.md manual, session-snapshot.json, and state files. Gap is no structured problem-solution capture. Integration fills the gap with /compound skill.

Bucket two, select. Current Namshub has read-docs-reminder static and docs-navigator with thirty keywords. Gap is no search over accumulated solutions. Integration fills the gap with grep in /build plus hook.

Bucket three, compress. Current Namshub has Claude's native compaction. Adequate, no change needed.

Bucket four, isolate. Current Namshub has twenty-two skills, subagent windows, worktrees, and per-session state. Strong implementation, no change needed.



Evidence of Cross-Session Knowledge Loss

Auto-approval saga -- thirteen commits.

First commit added permission request hook for exiting plan mode. Second added bash auto-approval for autonomous execution. Third added edit and write to permission request auto-approve. Fourth added pre-tool-use auto-approval for post-compaction issues. Fifth added permission request hook. Sixth removed permission decision reason from allow decisions. Seventh refactored hooks to consolidate auto-approval and add references. Eighth added user-level state check. Ninth preserved user-level state across sessions. Tenth enabled cross-directory auto-approval via session-id trust. Eleventh added multi-session auto-approval support. Twelfth corrected permission request hook filename. Thirteenth consolidated autonomous mode to /repair and /build.

Each session discovered one edge case. With a solutions knowledge base, session four would have known all remaining edge cases from sessions one through three.



PID-Scoping Build-and-Destroy

At two twenty-five PM, commit added PID-scoped state files -- four hundred seventy-three lines with confidence high.

Between those commits, a fix for macOS get-ancestor-pid basename.

At two fifty PM, commit removed broken PID-scoping -- sixty files modified.

The completion checkpoint reads confidence level high and what remains none -- for a feature entirely ripped out twenty-five minutes later. No record exists of why it failed, preventing future sessions from learning.



End of document.
