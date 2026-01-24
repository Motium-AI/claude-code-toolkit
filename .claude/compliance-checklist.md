Before stopping, complete these checks:

1. CLAUDE.md COMPLIANCE (if code written):
   - boring over clever, local over abstract
   - small composable units, stateless with side effects at edges
   - fail loud never silent, tests are truth
   - type hints everywhere, snake_case files, absolute imports
   - Pydantic for contracts, files < 400 lines, functions < 60 lines

2. DOCUMENTATION (if code written):
   - Read docs/index.md to understand the documentation structure
   - Identify ALL docs affected by your changes (architecture, API, operations, etc.)
   - Update those docs to reflect current implementation
   - Docs are the authoritative source - keep them accurate and current
   - Add new docs if you created new components/patterns not yet documented

3. UPDATE PROJECT .claude/MEMORIES.md (create if needed):
   This is NOT a changelog. Only add HIGH-VALUE entries:
   - User preferences that affect future work style
   - Architectural decisions with WHY (not what)
   - Non-obvious gotchas not documented elsewhere
   - Consolidate/update existing entries rather than append duplicates
   - If nothing significant learned, skip this step

4. TECHNICAL OVERVIEW (if architectural changes detected: not detected):
   - Read docs/TECHNICAL_OVERVIEW.md
   - Update sections affected by your changes
   - Add changelog entry with date
   - This is a living document - keep it current

6. COMMIT AND PUSH:
   - Stage all changes: git add -A
   - Commit with descriptive message summarizing the work
   - Push to remote: git push
   - If on a feature branch, consider opening a PR

After completing these checks, you may stop.