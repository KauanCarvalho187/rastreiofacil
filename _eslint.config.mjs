export default [
  {
    files: ["static/app.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        window: "readonly", document: "readonly", fetch: "readonly",
        localStorage: "readonly", location: "readonly", console: "readonly",
        setInterval: "readonly", setTimeout: "readonly", URL: "readonly",
        Blob: "readonly", alert: "readonly", confirm: "readonly",
        XMLHttpRequest: "readonly", navigator: "readonly", XLSX: "readonly",
        AbortController: "readonly", atob: "readonly", btoa: "readonly"
      }
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "warn",
      "no-dupe-keys": "error",
      "no-unreachable": "error",
      "no-const-assign": "error",
      "no-redeclare": "error",
      "no-constant-condition": "warn",
      "no-empty": "warn",
      "no-extra-semi": "warn",
      "no-func-assign": "error"
    }
  }
];
