---
description: Exhaustive audit of all Markdown documentation for gaps, staleness, and structure
---

## Execution Strategy

**CRITICAL: Use plan mode and parallel agents for this audit.**

### Phase 1: Strategic Exploration (Plan Mode)
Use `EnterPlanMode` to research before generating findings. Launch up to 3 parallel `Task` agents with `subagent_type=Explore`:

**Agent 1 - Documentation Inventory:**
- Glob all .md files in the repo (not just /docs)
- Map documentation structure and folder hierarchy
- Check all internal links for validity

**Agent 2 - Code Coverage Analysis:**
- Identify all top-level modules/packages
- Check which have corresponding documentation
- Note undocumented public APIs and features

**Agent 3 - Staleness Detection:**
- Find references to removed/renamed files or modules
- Identify outdated patterns, old file paths
- Check for deprecated terminology or features

### Phase 2: Synthesis
After agents return, synthesize findings in the plan file:
- Consolidate duplicate findings across agents
- Prioritize gaps by impact (onboarding, API consumers, operators)
- Identify structural reorganization opportunities

### Phase 3: Report Generation
Exit plan mode and generate the final report using the synthesized findings.

---

Conduct an exhaustive audit of ALL Markdown documentation files in this repository. Use ultrathink extended thinking to thoroughly analyze every finding.

**Scope: Leave No Stone Unturned.**
- Scan EVERY .md file in the repository, not just /docs — check root-level files, nested READMEs in subdirectories, inline documentation in /examples, /scripts, etc.
- Cross-reference EVERY major module, service, and workflow in the codebase against existing documentation.
- Read each document in full; do not skim or sample.

**Your Priorities (in order):**

**1. Structure & Organization Audit (Exhaustive):**
Map the complete documentation landscape:
- Catalog every .md file in the repo with its location and apparent purpose.
- Is there a clear entry point (README.md) that orients new readers?
- Is there a logical folder structure (e.g., /docs/guides, /docs/api, /docs/architecture)?
- Are documents at the right granularity (not everything in one mega-file, not fragmented into dozens of tiny files)?
- Is there an index or table of contents that provides navigation across ALL docs?
- Are related topics linked to each other, or do docs exist as isolated islands?
- Check every internal link — flag any that are broken or point to moved/renamed files.

**2. Gap Analysis (Code vs. Docs) — Comprehensive Coverage:**
Systematically scan the actual codebase and verify documentation exists for:
- Every top-level module and package
- Every service, API route, or endpoint
- Every significant workflow or user-facing feature
- Every integration with external systems
- Every environment or deployment configuration
- Every non-obvious convention or pattern used repeatedly in the code

Do not assume documentation exists. Verify it. For each major code area, explicitly confirm: "Documentation exists at X" or "NO DOCUMENTATION FOUND."

**3. Redundancy & Fragmentation (Full Inventory):**
Identify ALL documentation debt:
- Duplicate content explaining the same concept in multiple places (list every instance)
- Contradictory information across different files (quote the conflicts)
- Orphaned docs that are no longer linked from anywhere
- Stale sections that reference removed features, deprecated patterns, old file paths, or renamed modules
- Documents that have grown too long and should be split
- Empty or placeholder docs that were never filled in

**4. Filter Noise (Abstraction Level):**
Ignore low-level implementation details (function parameters, variable names, specific class methods) unless they are critical to the overall system design. The documentation should explain the System, not replicate the Code.

**5. Content Enrichment Requirements:**
For EVERY documentation gap identified, draft Markdown content that covers:
- **The "Why"**: The business intent or architectural reasoning behind the module.
- **The "How"**: High-level data flow, key relationships between services, and state management.
- **The "Gotchas"**: Critical system-wide invariants, side effects (DB/Network), and non-obvious dependencies.

**6. Audience & Discoverability (Complete Assessment):**
Assess whether docs serve ALL intended readers:
- Can a new developer onboard using only the docs? Walk through it step-by-step and note every gap.
- Can an external API consumer find what they need without reading internal architecture docs?
- Can an operator deploy, monitor, and troubleshoot using the docs?
- Are there missing doc types? Check for: quickstart, installation, configuration reference, troubleshooting, ADRs (architectural decision records), runbooks, changelog, contributing guide, API reference.

**Output Format:**

**Part A — Complete Documentation Inventory:**
```
Files Found: <total count>
<full tree view of ALL .md files in repo with line counts>

Broken Internal Links:
- <source file> → <broken link target> (line X)
- ...

Orphaned Files (not linked from anywhere):
- <file path>
- ...
```

**Part B — Structural Recommendations:**
```
Current Structure: <tree view of existing /docs and root-level .md files>
Proposed Structure:
   /docs
   ├── index.md              <- Central navigation hub
   ├── getting-started.md    <- Onboarding quickstart
   ├── architecture/
   │   ├── overview.md
   │   └── ...
   ├── guides/
   │   └── ...
   └── api/
       └── ...

Reorganization Actions:
- <MOVE: old/path.md → new/path.md — reason>
- <MERGE: file1.md + file2.md → combined.md — reason>
- <SPLIT: monolith.md → section1.md, section2.md — reason>
- <DELETE: orphaned-doc.md — reason>
- <CREATE: missing-doc.md — purpose and what it should cover>
```

**Part C — Content Findings (Every Issue):**
Report EVERY finding, not just the most important ones:
```
Finding #<N>
Target File: <path to existing .md file> or <suggestion for new .md file>
Category: <Gap | Outdated | Redundant | Contradictory | Misplaced | Missing Links | Incomplete>
Severity: <Critical | Warning | Advisory>
The Discrepancy: <Detailed explanation of what the code does vs. what the docs say, or structural issue — include specific file paths, function names, or features involved>
Suggested Update (Markdown):

## <Section Title>
<Proposed documentation text that resolves the discrepancy>
```

**Part D — Proposed Index:**
Generate a complete index.md (or update README.md) that serves as the documentation entry point with:
- Brief repo description
- Links to ALL doc sections with one-line descriptions
- "Start here" guidance for different audiences (new contributors, API consumers, operators)
- Quick reference to most critical docs

**Part E — Summary Statistics:**
```
Total .md files: X
Total gaps found: X
Total outdated sections: X
Total redundancies: X
Total broken links: X
Documentation coverage estimate: X% of major modules documented
Priority fixes (ranked by impact):
1. ...
2. ...
3. ...
```

**Completeness Check:**
Before finalizing your report, verify:
- [ ] Every top-level directory in the codebase was checked for corresponding docs
- [ ] Every .md file in the repo was read and cataloged
- [ ] Every internal link was validated
- [ ] Every finding includes a concrete suggested fix, not just a description of the problem
