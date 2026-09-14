import { useCallback } from "react";
import { authApi, type LoginRequest, type SignupRequest } from "../api/auth";
import { clearAuthToken, setAuthToken } from "../api/tokenStorage";
import { useUser } from "../state/UserContext";

// DEV-ONLY demo login — lets /login → /onboarding → /home be exercised before the backend exists.
// Never active in a production build (gated on import.meta.env.DEV). To remove once real auth is
// connected: delete this const, isDemoLogin, the `if` in login() below, and loginDemo — then drop
// the "데모 계정으로 시작하기" button + isDemo branch in LoginPage.tsx.
const DEMO_LOGIN = { id: "est", password: "1234" };
function isDemoLogin(payload: LoginRequest): boolean {
  return import.meta.env.DEV && payload.id === DEMO_LOGIN.id && payload.password === DEMO_LOGIN.password;
}

// The only place that should call authApi and touch tokenStorage — pages/components should go
// through this hook instead of calling src/api/auth.ts directly, so token handling stays in one spot.
export function useAuth() {
  const { isAuthenticated, setAuthenticated, setProfile } = useUser();

  // Returns whether the login was the DEV-only demo account, so callers (LoginPage) can route a
  // demo sign-in through /onboarding instead of straight to /home. Always false in production.
  const login = useCallback(
    async (payload: LoginRequest): Promise<boolean> => {
      if (isDemoLogin(payload)) {
        setAuthToken("dev-demo-token");
        setProfile({ name: "데모 사용자", email: "demo@gongnong.kr" });
        setAuthenticated(true);
        return true;
      }
      const res = await authApi.login(payload);
      setAuthToken(res.accessToken);
      setProfile({ name: res.user.name, email: res.user.email });
      setAuthenticated(true);
      return false;
    },
    [setAuthenticated, setProfile],
  );

  // DEV-ONLY convenience for a "데모 계정으로 시작하기" button — just calls login() with the demo
  // credentials so it goes through the exact same path as typing them into the form.
  const loginDemo = useCallback(() => login(DEMO_LOGIN), [login]);

  const signup = useCallback(
    async (payload: SignupRequest) => {
      const res = await authApi.signup(payload);
      setAuthToken(res.accessToken);
      setProfile({ name: res.user.name, email: res.user.email });
      setAuthenticated(true);
    },
    [setAuthenticated, setProfile],
  );

  const logout = useCallback(() => {
    clearAuthToken();
    setAuthenticated(false);
  }, [setAuthenticated]);

  return { isAuthenticated, login, loginDemo, signup, logout };
}
