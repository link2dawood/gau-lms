import type { Config } from 'tailwindcss';

/**
 * Design tokens are declared as CSS custom properties in app/globals.css and
 * referenced here, so GAU branding (task 4.5) is applied by changing variable
 * values rather than by editing components.
 */
const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        'surface-muted': 'rgb(var(--color-surface-muted) / <alpha-value>)',
        ink: 'rgb(var(--color-ink) / <alpha-value>)',
        'ink-muted': 'rgb(var(--color-ink-muted) / <alpha-value>)',
        navy: 'rgb(var(--color-navy) / <alpha-value>)',
        accent: 'rgb(var(--color-accent) / <alpha-value>)',
        border: 'rgb(var(--color-border) / <alpha-value>)',
        danger: 'rgb(var(--color-danger) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        serif: ['var(--font-serif)'],
      },
      maxWidth: {
        // Measure for long-form textbook prose. Reading comfort, not layout
        // convenience, decides this number.
        prose: '68ch',
      },
    },
  },
  plugins: [],
};

export default config;
