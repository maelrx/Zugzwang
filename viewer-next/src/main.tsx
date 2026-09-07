import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { applyAppearance, loadAppearance } from "@/lib/appearance";

// Apply before first paint so the stored theme/texture/font scale never flashes.
applyAppearance(loadAppearance());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
