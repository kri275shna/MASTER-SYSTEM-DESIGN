/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        purplle: {
          50: '#f9f5ff',
          100: '#f4ebff',
          200: '#e9d7fe',
          300: '#d6bbfb',
          400: '#b285fa',
          500: '#9b5de5', // Purplle Brand Color
          600: '#7b2cbf',
          700: '#5a189a',
          800: '#3c096c',
          900: '#240046',
        }
      }
    },
  },
  plugins: [],
}
