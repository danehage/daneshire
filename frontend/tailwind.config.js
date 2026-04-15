/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        cream: "var(--cream)",
        "warm-white": "var(--warm-white)",
        ink: "var(--ink)",
        "dark-brown": "var(--dark-brown)",
        "mid-brown": "var(--mid-brown)",
        "light-brown": "var(--light-brown)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "warm-tan": "var(--warm-tan)",
        error: "var(--error)",
        warning: "var(--warning)",
        success: "var(--success)",
      },
      fontFamily: {
        serif: ["Georgia", "Times New Roman", "serif"],
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "system-ui", "sans-serif"],
      },
      borderWidth: {
        "3": "3px",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
