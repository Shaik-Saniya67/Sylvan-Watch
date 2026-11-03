import type { Config } from "tailwindcss";

// French-inspired bright palette. "ink" is a deep green-brown rather than black.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ivory: "#FBF6EC", paper: "#FFFDF8", ink: "#33403A", muted: "#6B766F",
        sky: "#CFE5F5", lavender: "#DCD3F2", mint: "#CDEBDD", coral: "#FF7B6B",
        butter: "#FBE9A6", peach: "#FFD9C2", line: "#E8DFCC",
      },
      fontFamily: {
        display: ['"Iowan Old Style"', '"Palatino Linotype"', "Palatino", "Georgia", "serif"],
        sans: ["ui-sans-serif", "system-ui", '"Segoe UI"', "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
      boxShadow: { soft: "0 10px 30px -12px rgba(51,64,58,0.25)" },
    },
  },
  plugins: [],
};
export default config;
