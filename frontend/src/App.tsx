import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppProvider } from "./state/AppContext";
import { ModalProvider } from "./state/ModalContext";
import AppLayout from "./components/feature/AppLayout";
import ModalRoot from "./components/feature/modals/ModalRoot";
import ConfirmDeleteOverlay from "./components/feature/ConfirmDeleteOverlay";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import OnboardingPage from "./pages/OnboardingPage";
import HomePage from "./pages/HomePage";
import HistoryPage from "./pages/HistoryPage";
import MyPage from "./pages/MyPage";
import ProcessingPage from "./pages/ProcessingPage";
import PlayerPage from "./pages/PlayerPage";
import RequireAuth from "./routes/RequireAuth";
import RequireOnboarding from "./routes/RequireOnboarding";

export default function App() {
  return (
    <AppProvider>
      <ModalProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<RequireOnboarding />}>
                <Route element={<AppLayout />}>
                  <Route path="/home" element={<HomePage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/mypage" element={<MyPage />} />
                </Route>
                <Route path="/processing" element={<ProcessingPage />} />
                <Route path="/player" element={<PlayerPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ModalRoot />
          <ConfirmDeleteOverlay />
        </BrowserRouter>
      </ModalProvider>
    </AppProvider>
  );
}
