/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0a', 
        surface: '#111111',    
        primary: '#ffffff',    
        accent: '#3b82f6',     
        border: '#222222',     
      },
    },
  },
  plugins: [],
}