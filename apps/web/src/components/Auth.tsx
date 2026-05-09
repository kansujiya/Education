import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { getToken, setToken as storeToken } from "../api/client";

interface AuthCtxValue {
  token: string | null;
  setToken: (t: string | null) => void;
}

const AuthCtx = createContext<AuthCtxValue>({ token: null, setToken: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);

  useEffect(() => {
    setTokenState(getToken());
  }, []);

  const setToken = useCallback((t: string | null) => {
    storeToken(t);
    setTokenState(t);
  }, []);

  return <AuthCtx.Provider value={{ token, setToken }}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthCtxValue {
  return useContext(AuthCtx);
}
