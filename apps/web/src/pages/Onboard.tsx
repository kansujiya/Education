import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, setProfile } from "../api/client";

export function OnboardPage() {
  const [examId, setExamId] = useState("aws-ccp");
  const [examDate, setExamDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(60);
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await setProfile({
        exam_id: examId,
        exam_date: new Date(examDate).toISOString(),
        daily_minutes: dailyMinutes,
        language,
      });
      nav("/plan");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Onboarding</h1>
      <p className="muted">Tell the Coach what you're preparing for.</p>
      <form className="card" onSubmit={submit}>
        <label htmlFor="exam">Exam</label>
        <input id="exam" value={examId} onChange={(e) => setExamId(e.target.value)} required />

        <label htmlFor="date">Exam date</label>
        <input
          id="date"
          type="date"
          value={examDate}
          onChange={(e) => setExamDate(e.target.value)}
          required
        />

        <label htmlFor="minutes">Daily study minutes</label>
        <input
          id="minutes"
          type="number"
          min={15}
          max={600}
          value={dailyMinutes}
          onChange={(e) => setDailyMinutes(Number(e.target.value))}
          required
        />

        <label htmlFor="lang">Language</label>
        <select
          id="lang"
          value={language}
          onChange={(e) => setLanguage(e.target.value as "en" | "hi")}
          style={{ padding: 8, borderRadius: 6, background: "var(--panel)", color: "white", border: "1px solid #334155" }}
        >
          <option value="en">English</option>
          <option value="hi">Hindi</option>
        </select>

        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy} style={{ marginTop: 12 }}>
          {busy ? "Saving..." : "Continue"}
        </button>
      </form>
    </div>
  );
}
