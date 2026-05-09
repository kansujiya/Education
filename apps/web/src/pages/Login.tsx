import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, login, signup } from "../api/client";
import { useAuth } from "../components/Auth";

type Mode = "login" | "signup";

export function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { setToken } = useAuth();
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const fn = mode === "login" ? login : signup;
      const res = await fn(email, password);
      setToken(res.token);
      nav("/onboard");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Education AI</h1>
      <p className="muted">Outcome-focused exam prep.</p>
      <form className="card" onSubmit={submit}>
        <h2>{mode === "login" ? "Log in" : "Create an account"}</h2>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="password">Password (≥ 8 chars)</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />
        {error && <p className="error">{error}</p>}
        <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
          <button type="submit" disabled={busy}>
            {busy ? "..." : mode === "login" ? "Log in" : "Sign up"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            style={{ background: "transparent", color: "var(--muted)" }}
          >
            {mode === "login" ? "Need an account?" : "Already registered?"}
          </button>
        </div>
      </form>
    </div>
  );
}
