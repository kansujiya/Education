import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getPlan } from "../api/client";
import { useAuth } from "../components/Auth";

type Status = "loading" | "no-profile" | "ready";

export function HomePage() {
  const { token } = useAuth();
  const [status, setStatus] = useState<Status>("loading");
  const [examId, setExamId] = useState<string | null>(null);
  const [daysToExam, setDaysToExam] = useState<number | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("no-profile");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const plan = await getPlan(1);
        if (cancelled) return;
        setExamId(plan.exam_id);
        setDaysToExam(plan.days_to_exam);
        setStatus("ready");
      } catch (err) {
        if (cancelled) return;
        // 404 from /v1/me/plan means no profile; anything else we surface as
        // "no profile" so the user goes through onboarding.
        if (err instanceof ApiError && err.status === 404) {
          setStatus("no-profile");
        } else {
          setStatus("no-profile");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div>
      <h1>Education AI</h1>
      <p className="muted">
        Outcome-focused exam prep. The agent teaches you, drills you on past-year
        questions, and packages a downloadable revision pack when you've mastered
        a topic.
      </p>

      {!token && (
        <div className="card">
          <h2>1. Sign in to begin</h2>
          <p className="muted">
            Create an account or log back in. Your progress, plan and downloads
            are scoped to your user.
          </p>
          <Link className="btn" to="/login">
            Log in / Sign up
          </Link>
        </div>
      )}

      {token && status === "no-profile" && (
        <div className="card">
          <h2>2. Tell the Coach about your exam</h2>
          <p className="muted">
            Pick the exam, the date, and how many minutes per day you can study.
            The Coach builds a 7-day plan weighted by past-paper frequency.
          </p>
          <Link className="btn" to="/onboard">
            Set up my profile
          </Link>
        </div>
      )}

      {token && status === "ready" && (
        <>
          <div className="card">
            <h2>You're set up ✓</h2>
            <p>
              Exam: <strong>{examId}</strong>
              {" — "}
              <span className="muted">{daysToExam} days to go</span>
            </p>
            <Link className="btn" to="/plan">
              Open today's plan
            </Link>
          </div>

          <div className="card">
            <h3>Demo flow</h3>
            <ol>
              <li>
                <Link to="/plan">Plan</Link> — pick a topic for today
              </li>
              <li>
                On the Topic page, <em>Issue cards</em>, then answer each one
              </li>
              <li>
                <Link to="/progress">Progress</Link> — watch mastery climb past
                80% and a topic become "mastered"
              </li>
              <li>
                <Link to="/insight">Insight</Link> — historical cutoffs,
                selection %, and topic heatmap with cited sources
              </li>
              <li>
                Back on the Topic page, <em>Download bundle</em> exports a ZIP
                with lesson + mind map + cards
              </li>
            </ol>
          </div>
        </>
      )}

      {token && status === "loading" && <p className="muted">Checking your status…</p>}

      <div className="card" style={{ background: "transparent", border: "1px solid #334155" }}>
        <h3>Tip</h3>
        <p className="muted">
          A correct answer must mention one of the card's <em>key points</em>;
          the Examiner agent grades against that rubric. Try answers like
          <code style={{ marginLeft: 6 }}>"pay-as-you-go and elasticity"</code>{" "}
          for the cloud-benefits card.
        </p>
      </div>
    </div>
  );
}
