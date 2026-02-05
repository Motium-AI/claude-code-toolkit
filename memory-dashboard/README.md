# Memory Telemetry Dashboard

Local Next.js dashboard for visualizing Claude Code memory system telemetry across all projects.

## Features

- **Health Overview**: KPI cards showing projects, memories, injections, effectiveness rate
- **Category Breakdown**: Bar chart of events by category (bugfix, gotcha, pattern, etc.)
- **Usage Distribution**: Histogram of memory usage frequency
- **Projects Table**: Sortable list of all projects with memory data
- **Events Explorer**: Filterable, searchable list of all memory events

## Quick Start

```bash
cd memory-dashboard
npm install
npm run dev
```

Open http://localhost:3456

## How It Works

1. **Data Source**: Reads memory events from `~/.claude/memory/*/events/`
2. **SQLite Cache**: Syncs data to `~/.claude/telemetry.db` for fast queries
3. **Auto-Sync**: Automatically syncs on first visit or via "Sync Now" button

## API Endpoints

- `POST /api/sync` - Sync memory data from filesystem to SQLite
- `GET /api/stats` - Get aggregated dashboard statistics
- `GET /api/projects` - List all projects with memory data
- `GET /api/events` - List events (supports `projectHash`, `category`, `search` filters)

## Tech Stack

- Next.js 14 (App Router)
- Tailwind CSS
- Recharts (charts)
- better-sqlite3 (database)
