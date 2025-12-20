/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Cyberpunk Void Base
        void: {
          DEFAULT: '#050508',
          50: '#0a0a0f',
          100: '#0f0f15',
          200: '#12121a',
          300: '#181820',
          400: '#1f1f2a',
          500: '#16161e',
        },
        // Neon Accents
        neon: {
          cyan: '#00ffcc',
          magenta: '#ff00aa',
          gold: '#ffcc00',
          blue: '#00aaff',
          violet: '#aa66ff',
        },
        // Text
        text: {
          primary: '#f0f0f5',
          secondary: '#a0a0b0',
          muted: '#606070',
        },
        // Borders
        border: {
          subtle: '#1a1a25',
          DEFAULT: '#252535',
          glow: 'rgba(0, 255, 204, 0.3)',
        },
      },
      fontFamily: {
        display: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 30px rgba(0, 255, 204, 0.1)',
        'glow-magenta': '0 0 30px rgba(255, 0, 170, 0.1)',
        'soft': '0 4px 20px rgba(0, 0, 0, 0.5)',
      },
      animation: {
        'float': 'float 3s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'fade-in': 'fadeIn 0.4s ease-out forwards',
        'slide-up': 'slideUp 0.3s ease-out forwards',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 255, 204, 0.2)' },
          '50%': { boxShadow: '0 0 40px rgba(0, 255, 204, 0.4)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-primary': 'linear-gradient(135deg, #00ffcc 0%, #00aaff 50%, #aa66ff 100%)',
        'gradient-secondary': 'linear-gradient(135deg, #ff00aa 0%, #ffcc00 100%)',
      },
    },
  },
  plugins: [],
}

