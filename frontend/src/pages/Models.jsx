// src/pages/Models.jsx — replaces pages/models.py
import PageShell from "../components/PageShell.jsx";

export default function Models() {
  return (
    <PageShell
      group="Catalog & Management"
      icon="🤖"
      title="Models"
      caption="See what's trained, how well it's performing, and roll back if needed."
      status="Not live yet — arrives in Week 8."
      roadmap={[
        "Version history table — trained date, accuracy, class count",
        "Per-class precision/recall, where available",
        "Activate or roll back a model version",
      ]}
    />
  );
}
