// src/pages/Admin.jsx — replaces pages/admin.py
import PageShell from "../components/PageShell.jsx";

export default function Admin() {
  return (
    <PageShell
      group="Catalog & Management"
      icon="⚙️"
      title="Admin"
      caption="Store settings, bulk edits, and manual overrides."
      status="Not live yet — arrives in Week 7."
      roadmap={[
        "Bulk price/inventory upload via CSV",
        "Manual stock adjustments",
        "Store-level settings — tax rate, store ID, and the like",
      ]}
    />
  );
}
