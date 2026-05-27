// ESLint flat config for the brain.js Three.js scene.
// Goal: catch real bugs (TDZ, undeclared globals, unused vars) at the
// command line BEFORE we deploy to Firebase, instead of finding them by
// staring at a blank screen.

import globals from "globals";

export default [
  {
    files: ["web/brain.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        ...globals.browser,
        // Three.js is loaded via the HTML importmap, treat its imports
        // as resolved at runtime (eslint can't follow CDN URLs).
      },
    },
    rules: {
      "no-use-before-define": ["error", { "functions": false, "classes": true, "variables": true }],
      "no-undef": "error",
      "no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_" }],
      "no-redeclare": "error",
      "no-const-assign": "error",
      "no-dupe-keys": "error",
      "no-unreachable": "error",
    },
  },
];
