import { useEffect, useState } from "react";
import { ApiError, getInsights } from "../api/client";
import type { InsightPanel } from "../api/types";

export function InsightPage() {
  const [panel, setPanel] = useState<InsightPanel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInsights("aws-ccp")
      .then(setPanel)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!panel) return <p className="muted">Loading…</p>;

  const maxCount = Math.max(1, ...panel.heatmap.map((h) => h.pyq_count));
  return (
    <div>
      <h1>Historical insight · {panel.exam_id}</h1>

      <div className="card">
        <h2>Cutoffs</h2>
        <table style={{ width: "100%" }}>
          <thead>
            <tr><th>Year</th><th>Cutoff</th><th>Source</th></tr>
          </thead>
          <tbody>
            {panel.cutoffs.map((c) => (
              <tr key={c.year}>
                <td>{c.year}</td>
                <td>{c.cutoff_score}/{c.max_score}</td>
                <td className="muted">{c.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Selection %</h2>
        <table style={{ width: "100%" }}>
          <thead>
            <tr><th>Year</th><th>%</th><th>Source</th></tr>
          </thead>
          <tbody>
            {panel.selection_pct.map((s) => (
              <tr key={s.year}>
                <td>{s.year}</td>
                <td>{s.pct}{s.estimated && <span className="warn"> (est.)</span>}</td>
                <td className="muted">{s.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Topic heatmap</h2>
        {panel.heatmap.map((h) => (
          <div key={h.topic_id} style={{ display: "flex", alignItems: "center", gap: 8, margin: "4px 0" }}>
            <div style={{ width: 200 }}>{h.topic_id}</div>
            <div className="bar-track" style={{ flex: 1 }}>
              <div className="bar-fill" style={{ width: `${(h.pyq_count / maxCount) * 100}%` }} />
            </div>
            <span style={{ width: 24, textAlign: "right" }}>{h.pyq_count}</span>
          </div>
        ))}
      </div>

      <p className="muted">Sources: {panel.sources.join(" | ")}</p>
    </div>
  );
}
