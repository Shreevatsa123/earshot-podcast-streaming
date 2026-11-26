import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { loadConfig } from "./lib/config";
import "./index.css";

// Load the runtime config (CONTEXT §9) before rendering, so the API client and the
// auth layer (M1-05) get apiUrl and the Cognito values from config.json, not the bundle.
async function bootstrap() {
  await loadConfig();
  const root = document.getElementById("root");
  if (!root) throw new Error("#root element not found");
  createRoot(root).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
}

void bootstrap();
