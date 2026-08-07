// src/App.jsx
// React equivalent of app.py — routes replace the st.sidebar.radio switch.

import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";

import Checkout from "./pages/Checkout.jsx";
import Inventory from "./pages/Inventory.jsx";
import Alerts from "./pages/Alerts.jsx";
import Admin from "./pages/Admin.jsx";
import AddItem from "./pages/AddItem.jsx";
import Models from "./pages/Models.jsx";

export default function App() {
  return (
    <div className="bb-layout">
      <Sidebar />
      <main className="bb-main">
        <Routes>
          <Route path="/" element={<Navigate to="/checkout" replace />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/add-item" element={<AddItem />} />
          <Route path="/models" element={<Models />} />
          <Route path="*" element={<Navigate to="/checkout" replace />} />
        </Routes>
      </main>
    </div>
  );
}
