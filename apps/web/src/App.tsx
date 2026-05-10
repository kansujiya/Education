import {
  BrowserRouter,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import { AuthProvider, useAuth } from "./components/Auth";
import { HomePage } from "./pages/Home";
import { InsightPage } from "./pages/Insight";
import { LoginPage } from "./pages/Login";
import { OnboardPage } from "./pages/Onboard";
import { PlanPage } from "./pages/Plan";
import { ProgressPage } from "./pages/Progress";
import { TopicPage } from "./pages/Topic";

function Protected() {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function Shell() {
  const { token, setToken } = useAuth();
  return (
    <div className="app">
      <nav className="topnav">
        <NavLink to="/" end>Home</NavLink>
        <NavLink to="/plan">Plan</NavLink>
        <NavLink to="/progress">Progress</NavLink>
        <NavLink to="/insight">Insight</NavLink>
        {token ? (
          <a
            href="#logout"
            style={{ marginLeft: "auto", color: "var(--muted)" }}
            onClick={(e) => {
              e.preventDefault();
              setToken(null);
            }}
          >
            Log out
          </a>
        ) : null}
      </nav>
      <Outlet />
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Protected />}>
              <Route path="/onboard" element={<OnboardPage />} />
              <Route path="/plan" element={<PlanPage />} />
              <Route path="/topic/:topicId" element={<TopicPage />} />
              <Route path="/progress" element={<ProgressPage />} />
              <Route path="/insight" element={<InsightPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
