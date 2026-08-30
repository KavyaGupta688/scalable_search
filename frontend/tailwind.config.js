/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: '#0d131a',
          surface: '#131b26',
          elevated: '#1a2433',
          hover: '#223044',
          input: '#0a0f15',
          border: '#1f2937',
          borderStrong: '#2b3b52',
          borderSubtle: '#192330',
          brand: '#1428a0',
          brandHover: '#1c34c5',
          brandSubtle: '#1428a020',
          brandText: '#60a5fa',
          textPrimary: '#f8fafc',
          textSecondary: '#94a3b8',
          textMuted: '#64748b',
          success: '#4ade80',
          warning: '#f59e0b',
          danger: '#f87171',
        },
        modality: {
          image: '#38bdf8',
          video: '#a78bfa',
          document: '#fb923c',
          audio: '#4ade80',
          tabular: '#facc15'
        }
      },
      fontFamily: {
        sans: ['IBM Plex Sans', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        display: ['Georgia', 'Cambria', 'Times New Roman', 'serif']
      },
      borderRadius: {
        'xs': '2px',
        'sm': '4px',
        'md': '6px',
        'lg': '8px',
        'xl': '12px'
      }
    },
  },
  plugins: [],
}
