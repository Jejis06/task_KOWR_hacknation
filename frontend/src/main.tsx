import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ParcelPage } from "@/pages/ParcelPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ParcelPage />
  </StrictMode>,
);
