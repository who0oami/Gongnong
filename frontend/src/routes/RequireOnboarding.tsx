import { Navigate, Outlet } from "react-router-dom";
import { useUser } from "../state/UserContext";

// Sits inside RequireAuth, in front of home/history/mypage/processing/player: an authenticated
// user who hasn't finished onboarding (onboarding.view is only set by OnboardingPage's pickView,
// see UserContext/AppContext) is sent to /onboarding instead. Reuses the existing onboarding state
// rather than adding a separate "onboarded" flag — this also means a page refresh (which resets
// onboarding.view, since it isn't persisted) correctly sends the user through onboarding again.
export default function RequireOnboarding() {
  const { onboarding } = useUser();

  if (!onboarding.view) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
