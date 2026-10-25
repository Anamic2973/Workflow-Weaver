/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        weave: {
          50: "#f5f7ff",
          100: "#ebeeff",
          400: "#7c8cff",
          500: "#5b6bf5",
          600: "#4451db",
          700: "#3640b0",
          900: "#1f2358",
        },
      },
    },
  },
  plugins: [],
};
