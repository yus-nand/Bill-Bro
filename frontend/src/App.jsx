// src/App.jsx
// React equivalent of app.py — routes replace the st.sidebar.radio switch.

import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import TopBar from "./components/TopBar.jsx";
import TourOverlay from "./components/TourOverlay.jsx";
import { TrainingJobsProvider } from "./context/TrainingJobsContext.jsx";
import { AddItemDraftProvider } from "./context/AddItemDraftContext.jsx";
import { ToastProvider } from "./context/ToastContext.jsx";
import { TourProvider } from "./context/TourContext.jsx";

import Checkout from "./pages/Checkout.jsx";
import Inventory from "./pages/Inventory.jsx";
import Alerts from "./pages/Alerts.jsx";
import Admin from "./pages/Admin.jsx";
import AddItem from "./pages/AddItem.jsx";
import Models from "./pages/Models.jsx";

// Providers here (above <Routes>) mount once for the app's whole
// lifetime and never unmount on navigation — that's what makes
// training-job progress and Add Item's wizard state survive switching
// pages, instead of resetting every time their route unmounts. See
// context/TrainingJobsContext.jsx and context/AddItemDraftContext.jsx
// for why this state needed to move up here. TourProvider needs the
// same treatment for a different reason — a tour step can navigate the
// user across pages itself, and the overlay/progress would vanish
// mid-tour if it lived below the router.
// Fades each page in on route change. Keying on pathname forces React to
// remount the wrapper (not the page component itself — the Context
// providers above still keep AddItem/training state alive) so the
// animation restarts every navigation instead of only running once.
function AnimatedRoutes() {
  const location = useLocation();
  return (
    <div className="bb-page-fade" key={location.pathname}>
      <Routes location={location}>
        <Route path="/" element={<Navigate to="/checkout" replace />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/add-item" element={<AddItem />} />
        <Route path="/models" element={<Models />} />
        <Route path="*" element={<Navigate to="/checkout" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <TrainingJobsProvider>
        <AddItemDraftProvider>
          <TourProvider>
            <div className="bb-layout">
              <TopBar />
              <main className="bb-main">
                <AnimatedRoutes />
              </main>
            </div>
            <TourOverlay />
          </TourProvider>
        </AddItemDraftProvider>
      </TrainingJobsProvider>
    </ToastProvider>
  );
}
