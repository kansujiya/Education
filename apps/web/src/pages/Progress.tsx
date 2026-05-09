import { useEffect, useState } from "react";
import { ApiError, getProgress } from "../api/client";
import type { ProgressTopic } from "../api/types";

export function ProgressPage() {
  const [rows, setRows] = useState<ProgressTopic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProgress()
      .then((r) => setRows(r.topics))
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!rows) return <p className="muted">Loading…</p>;
  if (rows.length === 0)
    return <p className="muted">No progress yet — issue some cards and attempt them.</p>;

  return (
    <div>
      <h1>Progress</h1>
      {rows.map((r) => (
        <div key={r.topic_id} className="card">
          <strong>{r.topic_id}</strong>
          <div className="bar-track" style={{ marginTop: 6 }}>
            <div className="bar-fill" style={{ width: `${(r.mastery * 100).toFixed(0)}%` }} />
          </div>
          <p className="muted" style={{ marginTop: 6 }}>
            mastery {(r.mastery * 100).toFixed(1)}% · last touched {r.last_touched.slice(0, 16).replace("T", " ")}
          </p>
        </div>
      ))}
    </div>
  );
}
