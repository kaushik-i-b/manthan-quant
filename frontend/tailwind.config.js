/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B1220",
        panel: "#151F30",
        surface: "#1E293B",
        bord: "#334155",
        ink: "#F8FAFC",
        muted: "#94A3B8",
        profit: "#10B981",
        loss: "#EF4444",
        warn: "#F59E0B",
        accent: "#22D3EE",
      },
    },
  },
  plugins: [],
};
