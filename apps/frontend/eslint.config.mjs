import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";

/**
 * ESLint 9 flat config (required since eslint@9).
 * CRA/craco still applies its own lint rules during `yarn start` / `yarn build`.
 */
export default [
  { ignores: ["build/**", "node_modules/**", "public/**", "plugins/**"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      // CRA injects `process.env.*` at build-time; treat `process` as readonly global for linting.
      globals: { ...globals.browser, ...globals.es2021, process: "readonly" },
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { react, "react-hooks": reactHooks },
    rules: {
      // Prevent `no-unused-vars` false positives for JSX-only usage.
      "react/jsx-uses-vars": "error",
      // React 17+ new JSX transform: many files still import React; ignore that var if unused.
      "no-unused-vars": [
        "error",
        {
          varsIgnorePattern: "^(React)$",
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      ...reactHooks.configs.recommended.rules,
    },
    settings: { react: { version: "detect" } },
  },
  // Jest globals for unit tests
  {
    files: ["src/**/__tests__/**/*.{js,jsx}", "src/**/*.{test,spec}.{js,jsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node, ...globals.es2021, ...globals.jest, process: "readonly" },
    },
  },
];
