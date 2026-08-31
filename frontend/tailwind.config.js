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
        prism: {
          bg: 'var(--bg-app)', surface: 'var(--bg-surface)', elevated: 'var(--bg-surface-elevated)',
          hover: 'var(--bg-surface-hover)', input: 'var(--bg-input)', border: 'var(--border-default)',
          borderStrong: 'var(--border-strong)', borderSubtle: 'var(--border-subtle)', brand: 'var(--brand-primary)',
          brandHover: 'var(--brand-primary-hover)', brandSubtle: 'var(--brand-primary-subtle)', brandText: 'var(--brand-primary-text)',
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
