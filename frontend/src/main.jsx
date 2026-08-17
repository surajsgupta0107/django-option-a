import React from "react";
import ReactDOM from "react-dom/client";
import App from "./ServerUtilizationApp.jsx";
import { OwnerResponsePage } from "./ServerUtilizationApp.jsx";

// No routing library — this app has exactly two possible pages, so a plain path
// check is simpler and clearer than pulling in react-router for one branch. The
// backend route this depends on lives in config/urls.py (path("owner-response", ...)),
// which serves this same built bundle either way; the decision of *which* React
// component to mount happens entirely here, client-side.
const isOwnerResponsePage = window.location.pathname.replace(/\/+$/, "") === "/owner-response";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {isOwnerResponsePage ? <OwnerResponsePage /> : <App />}
  </React.StrictMode>
);
