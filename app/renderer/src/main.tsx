// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/main.tsx — renderer entry point.
import "./index.css";
import "./i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

const queryClient = new QueryClient();

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing in index.html");
createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
