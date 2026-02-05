# Search Tool Preference

Use Exa MCP tools for all web search:
- `web_search_exa` — general web search
- `get_code_context_exa` — code, GitHub, docs, Stack Overflow
- `company_research_exa` — company/vendor info

Do not use the built-in WebSearch tool. If Exa tools are not visible, discover them with `ToolSearch(query: 'exa')`.

# Documentation Search (QMD)

When QMD MCP is available, prefer semantic search over manual doc reading:

```bash
# Search for relevant docs
qmd_search "authentication flow"

# Get specific document
qmd_get "qmd://collection/path/to/doc.md"

# Check what's indexed
qmd_status
```

QMD is preferred because:
- Semantic matching finds conceptually related docs
- No need to read index.md first
- Token-efficient (returns excerpts, not full files)
- Works across any project with indexed docs

If QMD tools are not visible, fall back to reading `docs/index.md` manually.
