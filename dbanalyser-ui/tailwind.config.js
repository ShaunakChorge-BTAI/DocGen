/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#630ed4", container: "#7c3aed", fixed: "#ede9fe" },
        surface: {
          DEFAULT: "#f7f9fb",
          low: "#f2f4f6",
          lowest: "#ffffff",
        },
        "on-surface": "#1a1625",
        "on-surface-variant": "#4a4455",
        success: "#10b981",
        warning: "#f59e0b",
        error: "#ef4444",
        critical: "#dc2626",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Berkeley Mono", "JetBrains Mono", "monospace"],
      },
      borderRadius: { lg: "1rem", xl: "1.25rem" },
      boxShadow: {
        card: "0 2px 40px 0 rgba(90,0,198,0.05)",
        float: "0 8px 40px 0 rgba(90,0,198,0.10)",
      },
    },
  },
  plugins: [],
}

