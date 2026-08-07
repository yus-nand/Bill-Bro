// src/pages/AddItem.jsx — replaces pages/add_item.py
import PageShell from "../components/PageShell.jsx";

export default function AddItem() {
  return (
    <PageShell
      group="Catalog & Management"
      icon="➕"
      title="Add Item"
      caption="Bring a new product online, from photo to price tag."
      status="Not live yet — arrives in Week 4."
      roadmap={[
        "Item info form — name, category, price",
        "Capture or upload training photos",
        "Upload photos via POST /training/upload_images",
        "Track progress with GET /training/job/{job_id}",
      ]}
    />
  );
}
