import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";
import "@/index.css";

const rootElement = document.getElementById("root");

if (rootElement === null) {
  throw new Error("Eylo Console root element is missing.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
