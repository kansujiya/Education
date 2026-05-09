import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getPlan } from "../api/client";
import type { StudyPlan } from "../api/types";

export function PlanPage() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPlan(7)
      .then(setPlan)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!plan) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h1>Your plan</h1>
      <p className="muted">
        Exam <strong>{plan.exam_id}</strong> on {plan.exam_date} · {plan.days_to_exam} days to go ·{" "}
        {plan.daily_minutes} min/day
      </p>
      {plan.days.map((day) => (
        <div key={day.date} className="card">
          <strong>{day.date}</strong>
          {day.topics.length === 0 ? (
            <p className="muted">Rest day.</p>
          ) : (
            <ul style={{ marginTop: 8 }}>
              {day.topics.map((t) => (
                <li key={t.topic_id}>
                  <Link to={`/topic/${encodeURIComponent(t.topic_id)}`}>{t.title}</Link>{" "}
                  <span className="muted">({t.minutes} min)</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
