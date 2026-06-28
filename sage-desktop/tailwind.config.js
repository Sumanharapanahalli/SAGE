/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sage: {
          50: "#f4f7f5",
          100: "#dde7df",
          500: "#4a7c59",
          600: "#3e6a4a",
          700: "#32563c",
          900: "#1b2f22",
        },
      },
    },
  },
  plugins: [],
};
