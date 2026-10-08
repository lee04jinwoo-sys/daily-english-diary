/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'selector',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          50: '#faf9f6',
          100: '#f5f4f0',
          200: '#eceae4',
          300: '#dedad0',
          800: '#2c2b28',
          900: '#1c1b18',
        },
        notion: {
          bg: '#fcfbf9',
          sidebar: '#f7f6f3',
          card: '#ffffff',
          border: '#e9e8e4',
          text: '#37352f',
          subtext: '#787774',
          hover: '#efeee9',
          active: '#e5e4de',
        },
        darkpaper: {
          bg: '#191919',
          sidebar: '#202020',
          card: '#252525',
          border: '#333333',
          text: '#e6e6e6',
          subtext: '#9b9a97',
          hover: '#2c2c2c',
          active: '#363636',
        }
      },
      fontFamily: {
        serif: ['Lora', 'Georgia', 'serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
