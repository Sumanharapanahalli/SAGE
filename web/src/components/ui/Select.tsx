import React, { forwardRef } from 'react';
import { ChevronDown } from 'lucide-react';

// Select — a token-styled native <select>. Follows the ui/ primitive convention:
// inline React.CSSProperties consuming --sage-* tokens, forwardRef, an injected
// style tag (once) for the :focus-visible/:disabled pseudo-states Button uses too.
// The chevron is a lucide icon tinted via currentColor (= a token), so there is
// no hardcoded color anywhere.

type SelectSize = 'sm' | 'md' | 'lg';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  selectSize?: SelectSize;
}

if (typeof document !== 'undefined') {
  const STYLE_ID = 'sage-select-styles';
  if (!document.getElementById(STYLE_ID)) {
    const el = document.createElement('style');
    el.id = STYLE_ID;
    el.textContent = `
      .sage-select:focus-visible {
        outline: 2px solid var(--sage-accent);
        outline-offset: 1px;
        border-color: var(--sage-accent);
      }
      .sage-select:disabled { opacity: 0.55; cursor: not-allowed; }
    `;
    document.head.appendChild(el);
  }
}

const sizeStyles: Record<SelectSize, React.CSSProperties> = {
  sm: { fontSize: '0.75rem', padding: '0.25rem 1.75rem 0.25rem 0.5rem' },
  md: { fontSize: '0.875rem', padding: '0.4rem 2rem 0.4rem 0.625rem' },
  lg: { fontSize: '1rem', padding: '0.55rem 2.25rem 0.55rem 0.75rem' },
};

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ selectSize = 'md', style, className, children, ...rest }, ref) => {
    const baseStyle: React.CSSProperties = {
      appearance: 'none',
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      backgroundColor: 'var(--sage-surface)',
      color: 'var(--sage-text)',
      border: '1px solid var(--sage-border)',
      borderRadius: '0.375rem',
      lineHeight: 1.25,
      cursor: 'pointer',
      transition: 'border-color 0.15s ease',
      ...sizeStyles[selectSize],
      ...style,
    };
    return (
      <span
        style={{
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          color: 'var(--sage-text-muted)',
        }}
      >
        <select
          ref={ref}
          className={`sage-select${className ? ` ${className}` : ''}`}
          style={baseStyle}
          {...rest}
        >
          {children}
        </select>
        <ChevronDown
          size={14}
          aria-hidden="true"
          style={{ position: 'absolute', right: '0.5rem', pointerEvents: 'none' }}
        />
      </span>
    );
  }
);

Select.displayName = 'Select';

export { Select };
export type { SelectProps, SelectSize };
