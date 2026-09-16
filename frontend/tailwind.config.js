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
          bg: 'rgb(var(--nexus-bg) / <alpha-value>)',
          surface: 'rgb(var(--nexus-surface) / <alpha-value>)',
          elevated: 'rgb(var(--nexus-elevated) / <alpha-value>)',
          hover: 'rgb(var(--nexus-hover) / <alpha-value>)',
          input: 'rgb(var(--nexus-input) / <alpha-value>)',
          border: 'rgb(var(--nexus-border) / <alpha-value>)',
          borderStrong: 'rgb(var(--nexus-borderStrong) / <alpha-value>)',
          borderSubtle: 'rgb(var(--nexus-borderSubtle) / <alpha-value>)',
          brand: 'rgb(var(--nexus-brand) / <alpha-value>)',
          brandHover: 'rgb(var(--nexus-brandHover) / <alpha-value>)',
          brandSubtle: 'rgb(var(--nexus-brandSubtle) / <alpha-value>)',
          brandText: 'rgb(var(--nexus-brandText) / <alpha-value>)',
          textPrimary: 'rgb(var(--nexus-textPrimary) / <alpha-value>)',
          textSecondary: 'rgb(var(--nexus-textSecondary) / <alpha-value>)',
          textMuted: 'rgb(var(--nexus-textMuted) / <alpha-value>)',
          success: 'rgb(var(--nexus-success) / <alpha-value>)',
          warning: 'rgb(var(--nexus-warning) / <alpha-value>)',
          danger: 'rgb(var(--nexus-danger) / <alpha-value>)',
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
        sans: ['DM Sans', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        display: ['Bricolage Grotesque', 'DM Sans', 'sans-serif']
      },
      borderRadius: {
        'xs': '8px',
        'sm': '12px',
        'md': '14px',
        'lg': '20px',
        'xl': '26px'
      }
    },
  },
  plugins: [],
}
