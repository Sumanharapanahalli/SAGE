import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Token-driven: every sage-* utility resolves to the index.css CSS
        // variable, so the design tokens are the single source of truth (use
        // bg-sage-accent, text-sage-text-muted, border-sage-border, …).
        // Replaces the old unused green numeric palette.
        sage: {
          accent: 'var(--sage-accent)',
          'accent-hover': 'var(--sage-accent-hover)',
          'accent-light': 'var(--sage-accent-light)',
          'accent-text': 'var(--sage-accent-text)',
          surface: 'var(--sage-surface)',
          'surface-muted': 'var(--sage-surface-muted)',
          border: 'var(--sage-border)',
          text: 'var(--sage-text)',
          'text-muted': 'var(--sage-text-muted)',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
