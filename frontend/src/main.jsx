import React from "react";
import ReactDOM from "react-dom/client";
import { Root } from "./ServerUtilizationApp.jsx";

// All routing/auth-state logic (owner-response link vs login vs admin app vs owner
// dashboard) lives inside Root, in ServerUtilizationApp.jsx — this file just mounts it.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
