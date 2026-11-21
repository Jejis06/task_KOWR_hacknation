import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ParcelPage } from "@/pages/ParcelPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <TooltipProvider>
      <ParcelPage />
    </TooltipProvider>
  </StrictMode>,
);
