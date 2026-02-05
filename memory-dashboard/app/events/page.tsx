"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";

interface EventRecord {
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

function EventsContent() {
  const searchParams = useSearchParams();
  const initialProjectHash = searchParams.get("projectHash") || "";

  const [events, setEvents] = useState<EventRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [projectHash, setProjectHash] = useState(initialProjectHash);
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const limit = 20;

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(page * limit),
    });
    if (search) params.set("search", search);
    if (category) params.set("category", category);
    if (projectHash) params.set("projectHash", projectHash);

    const res = await fetch(`/api/events?${params}`);
    const data = await res.json();
    setEvents(data.events);
    setTotal(data.total);
    setLoading(false);
  }, [search, category, projectHash, page]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const formatDate = (ts: string) => {
    if (!ts) return "—";
    return new Date(ts).toLocaleString();
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Events
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {total} memory events
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <input
          type="text"
          placeholder="Search content..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(0);
          }}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          <option value="">All categories</option>
          <option value="bugfix">bugfix</option>
          <option value="gotcha">gotcha</option>
          <option value="pattern">pattern</option>
          <option value="refactor">refactor</option>
          <option value="architecture">architecture</option>
          <option value="config">config</option>
        </select>
        {projectHash && (
          <button
            onClick={() => {
              setProjectHash("");
              setPage(0);
            }}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-md text-sm hover:bg-gray-300 dark:hover:bg-gray-600"
          >
            Clear project filter
          </button>
        )}
      </div>

      {/* Events List */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="text-gray-500 dark:text-gray-400">Loading...</div>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            No events found
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4"
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-xs text-gray-500 dark:text-gray-400">
                      {event.id}
                    </span>
                    {event.category && (
                      <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded text-xs">
                        {event.category}
                      </span>
                    )}
                    {event.source && (
                      <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded text-xs">
                        {event.source}
                      </span>
                    )}
                  </div>
                  <p
                    className={`text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap ${
                      expandedId === event.id ? "" : "line-clamp-3"
                    }`}
                  >
                    {event.content}
                  </p>
                  {event.content.length > 200 && (
                    <button
                      onClick={() =>
                        setExpandedId(expandedId === event.id ? null : event.id)
                      }
                      className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 mt-1"
                    >
                      {expandedId === event.id ? "Show less" : "Show more"}
                    </button>
                  )}
                  {event.entities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {event.entities.slice(0, 8).map((entity, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded text-xs"
                        >
                          {entity}
                        </span>
                      ))}
                      {event.entities.length > 8 && (
                        <span className="text-xs text-gray-400">
                          +{event.entities.length - 8} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="text-right ml-4">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatDate(event.ts)}
                  </div>
                  <div className="mt-2 text-sm">
                    <span className="text-green-600 dark:text-green-400">
                      {event.injectedCount} inj
                    </span>
                    {" / "}
                    <span className="text-amber-600 dark:text-amber-400">
                      {event.citedCount} cited
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-gray-600 dark:text-gray-400">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default function EventsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500 dark:text-gray-400">Loading...</div>
        </div>
      }
    >
      <EventsContent />
    </Suspense>
  );
}
