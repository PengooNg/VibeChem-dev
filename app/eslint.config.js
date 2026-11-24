// SPDX-License-Identifier: GPL-3.0-or-later
// app/eslint.config.js — ESLint 9 flat config (typescript-eslint strict, React hooks, Vite refresh).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["out/", "node_modules/"] },
  js.configs.recommended,
  tseslint.configs.strict,
  {
    files: ["renderer/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    extends: [reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
  },
  {
    files: ["main/**/*.ts", "e2e/**/*.ts", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
);
