module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D1B2A',
        card: '#1B263B',
        accent: '#00D1FF',
      },
      boxShadow: {
        card: '0 2px 12px rgba(0,0,0,0.25)'
      }
    },
  },
  plugins: [],
}; 