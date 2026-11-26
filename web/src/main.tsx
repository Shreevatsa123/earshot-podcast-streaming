import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { SessionProvider } from "./auth/session";
import { loadConfig, USE_MOCKS } from "./lib/config";
import "./index.css";

// Load the runtime config (CONTEXT §9) before rendering, so the API client and the login
// get apiUrl and the Cognito values from config.json, not from the bundle.
async function bootstrap() {
  const config = await loadConfig();
  const root = document.getElementById("root");
  if (!root) throw new Error("#root element not found");
  createRoot(root).render(
    <StrictMode>
      <SessionProvider config={config} mock={USE_MOCKS}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SessionProvider>
    </StrictMode>,
  );
}

void bootstrap();
