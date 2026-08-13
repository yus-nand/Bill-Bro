// src/context/AddItemDraftContext.jsx
// Holds Add Item's own in-progress wizard state (which item was just
// created, what step you're on, staged photo Files) above the router —
// same reasoning as TrainingJobsContext, just for the pre-training part
// of the flow that context doesn't need to know about. File objects
// can't survive an actual browser reload (no way to serialize raw bytes
// into storage without real effort — IndexedDB blob storage — so this
// deliberately doesn't attempt that), but living in a Provider mounted
// above <Routes> means it DOES survive ordinary in-app navigation, which
// covers the common case: you're capturing photos, you jump to Inventory
// to check something, you come back — nothing's lost.

import { createContext, useContext, useState } from "react";

const emptyForm = {
  name: "",
  sku: "",
  price: "",
  category: "",
  expiry_date: "",
  low_stock_threshold: "5",
};

const AddItemDraftContext = createContext(null);

export function AddItemDraftProvider({ children }) {
  const [step, setStep] = useState("details"); // "details" | "capture"
  const [form, setForm] = useState(emptyForm);
  const [itemId, setItemId] = useState(null);
  const [images, setImages] = useState([]); // [{ file, previewUrl }]

  const resetDraft = () => {
    images.forEach((img) => URL.revokeObjectURL(img.previewUrl));
    setStep("details");
    setForm(emptyForm);
    setItemId(null);
    setImages([]);
  };

  const value = {
    step,
    setStep,
    form,
    setForm,
    itemId,
    setItemId,
    images,
    setImages,
    resetDraft,
    emptyForm,
  };

  return (
    <AddItemDraftContext.Provider value={value}>{children}</AddItemDraftContext.Provider>
  );
}

export function useAddItemDraft() {
  const ctx = useContext(AddItemDraftContext);
  if (!ctx) {
    throw new Error("useAddItemDraft must be used inside an AddItemDraftProvider");
  }
  return ctx;
}
