import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth.jsx";
import { AppearanceProvider } from "./lib/appearance.jsx";
import { PrefsProvider } from "./lib/prefs.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppearanceProvider>
        <AuthProvider>
          <PrefsProvider>
            <App />
          </PrefsProvider>
        </AuthProvider>
      </AppearanceProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// Offline shell: recently viewed pages and posters keep working on a flaky
// connection, which matters for something that runs on your own box.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
