/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#eefbf7',
          100: '#d5f5eb',
          200: '#aeebd9',
          300: '#79dbc2',
          400: '#43c4a6',
          500: '#1fa98c',
          600: '#148f74',
          700: '#11735f',
          800: '#115b4d',
          900: '#104b41',
        },
      },
    },
  },
  plugins: [],
}
