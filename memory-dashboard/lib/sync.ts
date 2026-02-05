import { readdirSync, readFileSync, existsSync, statSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { getDb } from "./db";

const MEMORY_DIR = join(homedir(), ".claude", "memory");

interface MemoryEvent {
  id: string;
  ts: string;
  type?: string;
  content?: string;
  entities?: string[];
  source?: string;
  category?: string;
  meta?: {
    quality?: string;
    files_changed?: string[];
  };
}

interface Manifest {
  project_hash?: string;
  total_count?: number;
  recent?: string[];
  updated_at?: string;
  utility?: {
    total_injected?: number;
    total_cited?: number;
    per_event?: Record<string, { injected?: number; cited?: number }>;
  };
}

export interface SyncResult {
  projectsScanned: number;
  eventsAdded: number;
  eventsUpdated: number;
  errors: string[];
}

export function syncMemoryData(): SyncResult {
  const db = getDb();
  const result: SyncResult = {
    projectsScanned: 0,
    eventsAdded: 0,
    eventsUpdated: 0,
    errors: [],
  };

  if (!existsSync(MEMORY_DIR)) {
    result.errors.push(`Memory directory not found: ${MEMORY_DIR}`);
    return result;
  }

  const projectDirs = readdirSync(MEMORY_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  for (const projectHash of projectDirs) {
    try {
      syncProject(db, projectHash, result);
      result.projectsScanned++;
    } catch (err) {
      result.errors.push(`Error syncing ${projectHash}: ${err}`);
    }
  }

  return result;
}

function syncProject(
  db: ReturnType<typeof getDb>,
  projectHash: string,
  result: SyncResult
) {
  const projectDir = join(MEMORY_DIR, projectHash);
  const manifestPath = join(projectDir, "manifest.json");
  const eventsDir = join(projectDir, "events");

  // Read manifest if exists
  let manifest: Manifest = {};
  if (existsSync(manifestPath)) {
    try {
      manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
    } catch {
      // Ignore parse errors
    }
  }

  // Extract project name from hash (we don't have git info here)
  const projectName = projectHash.slice(0, 8);

  // Count events
  let eventCount = 0;
  let lastEventAt = "";

  if (existsSync(eventsDir)) {
    const eventFiles = readdirSync(eventsDir).filter((f) => f.endsWith(".json"));
    eventCount = eventFiles.length;

    // Sync each event
    for (const eventFile of eventFiles) {
      try {
        const eventPath = join(eventsDir, eventFile);
        const eventData: MemoryEvent = JSON.parse(
          readFileSync(eventPath, "utf-8")
        );

        if (!eventData.id) continue;

        // Track latest event
        if (eventData.ts && eventData.ts > lastEventAt) {
          lastEventAt = eventData.ts;
        }

        // Get utility stats from manifest
        const utilityStats = manifest.utility?.per_event?.[eventData.id] || {};

        // Check if event exists
        const existing = db
          .prepare("SELECT id FROM events WHERE id = ?")
          .get(eventData.id);

        if (existing) {
          // Update utility counts
          db.prepare(
            `UPDATE events SET injected_count = ?, cited_count = ? WHERE id = ?`
          ).run(
            utilityStats.injected || 0,
            utilityStats.cited || 0,
            eventData.id
          );
          result.eventsUpdated++;
        } else {
          // Insert new event
          db.prepare(
            `INSERT INTO events (id, project_hash, ts, type, category, content, source, injected_count, cited_count)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
          ).run(
            eventData.id,
            projectHash,
            eventData.ts || "",
            eventData.type || "",
            eventData.category || "",
            (eventData.content || "").slice(0, 500),
            eventData.source || "",
            utilityStats.injected || 0,
            utilityStats.cited || 0
          );

          // Insert entities
          if (eventData.entities && eventData.entities.length > 0) {
            const insertEntity = db.prepare(
              `INSERT INTO event_entities (event_id, entity) VALUES (?, ?)`
            );
            for (const entity of eventData.entities) {
              insertEntity.run(eventData.id, entity);
            }
          }

          result.eventsAdded++;
        }
      } catch (err) {
        // Log but don't fail on malformed events
        console.error(`Error processing ${eventFile}:`, err);
      }
    }
  }

  // Upsert project
  db.prepare(
    `INSERT INTO projects (hash, name, event_count, last_event_at, total_injected, total_cited, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
     ON CONFLICT(hash) DO UPDATE SET
       event_count = excluded.event_count,
       last_event_at = excluded.last_event_at,
       total_injected = excluded.total_injected,
       total_cited = excluded.total_cited,
       updated_at = excluded.updated_at`
  ).run(
    projectHash,
    projectName,
    eventCount,
    lastEventAt,
    manifest.utility?.total_injected || 0,
    manifest.utility?.total_cited || 0
  );
}

export function getLastSyncTime(): string | null {
  const db = getDb();
  const row = db
    .prepare("SELECT value FROM sync_state WHERE key = 'last_sync'")
    .get() as { value: string } | undefined;
  return row?.value || null;
}

export function updateLastSyncTime() {
  const db = getDb();
  db.prepare(
    `INSERT INTO sync_state (key, value) VALUES ('last_sync', datetime('now'))
     ON CONFLICT(key) DO UPDATE SET value = excluded.value`
  ).run();
}
