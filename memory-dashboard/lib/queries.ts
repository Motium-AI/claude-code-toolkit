import { getDb } from "./db";

export interface ProjectStats {
  hash: string;
  name: string;
  eventCount: number;
  lastEventAt: string;
  totalInjected: number;
  totalCited: number;
  effectivenessRate: number;
}

export interface DashboardStats {
  totalProjects: number;
  totalEvents: number;
  totalInjections: number;
  totalCitations: number;
  effectivenessRate: number;
  categoryBreakdown: { category: string; count: number; cited: number }[];
  scoreDistribution: { bucket: string; count: number }[];
}

export interface EventRecord {
  id: string;
  projectHash: string;
  ts: string;
  type: string;
  category: string;
  content: string;
  source: string;
  injectedCount: number;
  citedCount: number;
  entities: string[];
}

export function getDashboardStats(): DashboardStats {
  const db = getDb();

  // Total counts
  const projectCount = db
    .prepare("SELECT COUNT(*) as count FROM projects")
    .get() as { count: number };

  const eventCount = db
    .prepare("SELECT COUNT(*) as count FROM events")
    .get() as { count: number };

  const totals = db
    .prepare(
      "SELECT SUM(total_injected) as injected, SUM(total_cited) as cited FROM projects"
    )
    .get() as { injected: number | null; cited: number | null };

  const totalInjected = totals.injected || 0;
  const totalCited = totals.cited || 0;

  // Category breakdown
  const categories = db
    .prepare(
      `SELECT category, COUNT(*) as count, SUM(cited_count) as cited
       FROM events
       WHERE category != ''
       GROUP BY category
       ORDER BY count DESC`
    )
    .all() as { category: string; count: number; cited: number }[];

  // Score distribution (using injected_count as proxy)
  const scoreDistribution = [
    { bucket: "Never used", count: 0 },
    { bucket: "1-5 injections", count: 0 },
    { bucket: "6-20 injections", count: 0 },
    { bucket: "20+ injections", count: 0 },
  ];

  const scoreBuckets = db
    .prepare(
      `SELECT
        CASE
          WHEN injected_count = 0 THEN 0
          WHEN injected_count <= 5 THEN 1
          WHEN injected_count <= 20 THEN 2
          ELSE 3
        END as bucket,
        COUNT(*) as count
       FROM events
       GROUP BY bucket`
    )
    .all() as { bucket: number; count: number }[];

  for (const row of scoreBuckets) {
    if (row.bucket >= 0 && row.bucket < scoreDistribution.length) {
      scoreDistribution[row.bucket].count = row.count;
    }
  }

  return {
    totalProjects: projectCount.count,
    totalEvents: eventCount.count,
    totalInjections: totalInjected,
    totalCitations: totalCited,
    effectivenessRate:
      totalInjected > 0 ? Math.round((totalCited / totalInjected) * 100) : 0,
    categoryBreakdown: categories,
    scoreDistribution,
  };
}

export function getProjects(): ProjectStats[] {
  const db = getDb();

  const rows = db
    .prepare(
      `SELECT hash, name, event_count, last_event_at, total_injected, total_cited
       FROM projects
       ORDER BY last_event_at DESC`
    )
    .all() as {
    hash: string;
    name: string;
    event_count: number;
    last_event_at: string;
    total_injected: number;
    total_cited: number;
  }[];

  return rows.map((row) => ({
    hash: row.hash,
    name: row.name,
    eventCount: row.event_count,
    lastEventAt: row.last_event_at,
    totalInjected: row.total_injected,
    totalCited: row.total_cited,
    effectivenessRate:
      row.total_injected > 0
        ? Math.round((row.total_cited / row.total_injected) * 100)
        : 0,
  }));
}

export function getEvents(options: {
  projectHash?: string;
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): { events: EventRecord[]; total: number } {
  const db = getDb();
  const { projectHash, category, search, limit = 50, offset = 0 } = options;

  let whereClause = "1=1";
  const params: (string | number)[] = [];

  if (projectHash) {
    whereClause += " AND e.project_hash = ?";
    params.push(projectHash);
  }

  if (category) {
    whereClause += " AND e.category = ?";
    params.push(category);
  }

  if (search) {
    whereClause += " AND (e.content LIKE ? OR e.id LIKE ?)";
    params.push(`%${search}%`, `%${search}%`);
  }

  // Get total count
  const countResult = db
    .prepare(`SELECT COUNT(*) as count FROM events e WHERE ${whereClause}`)
    .get(...params) as { count: number };

  // Get paginated events
  const rows = db
    .prepare(
      `SELECT e.id, e.project_hash, e.ts, e.type, e.category, e.content, e.source,
              e.injected_count, e.cited_count
       FROM events e
       WHERE ${whereClause}
       ORDER BY e.ts DESC
       LIMIT ? OFFSET ?`
    )
    .all(...params, limit, offset) as {
    id: string;
    project_hash: string;
    ts: string;
    type: string;
    category: string;
    content: string;
    source: string;
    injected_count: number;
    cited_count: number;
  }[];

  // Get entities for each event
  const getEntities = db.prepare(
    `SELECT entity FROM event_entities WHERE event_id = ?`
  );

  const events: EventRecord[] = rows.map((row) => {
    const entityRows = getEntities.all(row.id) as { entity: string }[];
    return {
      id: row.id,
      projectHash: row.project_hash,
      ts: row.ts,
      type: row.type,
      category: row.category,
      content: row.content,
      source: row.source,
      injectedCount: row.injected_count,
      citedCount: row.cited_count,
      entities: entityRows.map((e) => e.entity),
    };
  });

  return { events, total: countResult.count };
}
