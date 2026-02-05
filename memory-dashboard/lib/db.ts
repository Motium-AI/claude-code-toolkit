import Database from "better-sqlite3";
import { join } from "path";
import { homedir } from "os";

const DB_PATH = join(homedir(), ".claude", "telemetry.db");

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    initSchema(db);
  }
  return db;
}

function initSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS projects (
      hash TEXT PRIMARY KEY,
      name TEXT,
      event_count INTEGER DEFAULT 0,
      last_event_at TEXT,
      total_injected INTEGER DEFAULT 0,
      total_cited INTEGER DEFAULT 0,
      updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
      id TEXT PRIMARY KEY,
      project_hash TEXT,
      ts TEXT,
      type TEXT,
      category TEXT,
      content TEXT,
      source TEXT,
      injected_count INTEGER DEFAULT 0,
      cited_count INTEGER DEFAULT 0,
      FOREIGN KEY (project_hash) REFERENCES projects(hash)
    );

    CREATE TABLE IF NOT EXISTS event_entities (
      event_id TEXT,
      entity TEXT,
      FOREIGN KEY (event_id) REFERENCES events(id)
    );

    CREATE INDEX IF NOT EXISTS idx_entities ON event_entities(entity);
    CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_hash);
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
    CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

    CREATE TABLE IF NOT EXISTS injections (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT,
      project_hash TEXT,
      ts TEXT,
      event_id TEXT,
      score REAL,
      was_cited INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_injections_event ON injections(event_id);

    CREATE TABLE IF NOT EXISTS sync_state (
      key TEXT PRIMARY KEY,
      value TEXT
    );
  `);
}

export function closeDb() {
  if (db) {
    db.close();
    db = null;
  }
}
