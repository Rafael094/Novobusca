/** @type {import('tailwindcss').Config} */
module.exports = {
  // Dark mode driven by `body.dark` (same mechanism as CerberoFront).
  darkMode: ["selector", "body.dark"],
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary action color: IntelliINPI blue (#1A22CF). The scale is centred
        // on that token so every existing `brand-*` class across the app adopts
        // the blue theme without being rewritten.
        brand: {
          50: "#eef0ff",   // --primary-light
          100: "#dde1ff",
          200: "#c2c8ff",
          300: "#9aa3ff",
          400: "#6b76f7",
          500: "#1a22cf",  // --primary-color
          600: "#1a22cf",  // primary (buttons use 600 in the app)
          700: "#151ca8",  // --primary-hover
          800: "#12178a",
          900: "#10146f",
        },
        // The sidebar keeps the brand blue in both themes.
        sidebar: {
          DEFAULT: "#1a22cf",
          light: "#2b34e0",
          hover: "rgba(255,255,255,0.20)",
          border: "#151ca8",
          muted: "rgba(255,255,255,0.85)",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(0, 0, 0, 0.04), 0 1px 3px 0 rgba(0, 0, 0, 0.06)",
        soft: "0 4px 16px -4px rgba(0, 0, 0, 0.14)",
      },
      borderRadius: {
        xl: "0.75rem",
      },
    },
  },
  plugins: [],
};
