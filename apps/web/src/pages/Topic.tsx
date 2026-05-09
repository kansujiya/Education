import { useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, attemptCard, exportTopic, issueCards } from "../api/client";
import type { AttemptResponse, Card } from "../api/types";

export function TopicPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const [cards, setCards] = useState<Card[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, AttemptResponse>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function fetchCards() {
    if (!topicId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await issueCards(topicId);
      setCards(res.cards);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(cardId: string) {
    setError(null);
    try {
      const res = await attemptCard(cardId, answers[cardId] ?? "");
      setResults((prev) => ({ ...prev, [cardId]: res }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function downloadBundle() {
    if (!topicId) return;
    try {
      const res = await exportTopic(topicId, {
        topic_title: topicId,
        lesson_md: `# ${topicId}\n\nUse the cards below.`,
        mindmap_svg: "<svg/>",
        mindmap_mermaid: `mindmap\n  root((${topicId}))`,
      });
      window.open(res.url, "_blank");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  return (
    <div>
      <h1>{topicId}</h1>
      <p className="muted">
        Issue cards, attempt them, then export a downloadable bundle when you're confident.
      </p>
      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={fetchCards} disabled={busy}>
          {busy ? "Generating..." : cards ? "Re-issue" : "Issue cards"}
        </button>
        <button onClick={downloadBundle} disabled={!cards}>
          Download bundle
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {cards?.map((card) => (
        <div key={card.id} className="card">
          <strong>{card.type.toUpperCase()}</strong>{" "}
          {card.source_pyq_id && (
            <span className="muted">· source: {card.source_pyq_id}</span>
          )}
          <p>{card.prompt}</p>
          <textarea
            rows={2}
            value={answers[card.id] ?? ""}
            onChange={(e) => setAnswers((a) => ({ ...a, [card.id]: e.target.value }))}
            placeholder="Your answer…"
          />
          <div style={{ marginTop: 8 }}>
            <button onClick={() => submitAnswer(card.id)} disabled={!answers[card.id]?.trim()}>
              Submit
            </button>
            {results[card.id] && (
              <span style={{ marginLeft: 12 }}>
                {results[card.id].correct ? <span className="good">✓</span> : <span className="warn">✗</span>}{" "}
                score={results[card.id].score.toFixed(2)}{" "}
                {results[card.id].gap && <span className="muted">— {results[card.id].gap}</span>}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
