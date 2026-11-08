import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Earshot web (M1). Dev server runs on 5173 (a Cognito callback URL per CONTEXT §9).
// Build output goes to web/dist, which the Web construct (M1-04) deploys to S3/CloudFront.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    fs: {
      // Allow importing the committed fixtures from ../contracts/samples in mock mode.
      allow: [".", "../contracts"],
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
