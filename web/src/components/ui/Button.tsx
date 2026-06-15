import React, { forwardRef } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

// Inject styles once at module load — not inside render.
if (typeof document !== 'undefined') {
  const STYLE_ID = 'sage-btn-styles';
  if (!document.getElementById(STYLE_ID)) {
    const el = document.createElement('style');
    el.id = STYLE_ID;
    el.textContent = `
      @keyframes sage-btn-spin {
        to { transform: rotate(360deg); }
      }
      .sage-btn:focus-visible {
        outline: 2px solid var(--sage-accent);
        outline-offset: 2px;
      }
      .sage-btn--primary:not([disabled]):not([aria-disabled="true"]):hover {
        background-color: var(--sage-accent-hover);
      }
      .sage-btn--secondary:not([disabled]):not([aria-disabled="true"]):hover {
        background-color: var(--sage-accent);
        color: var(--sage-accent-text);
      }
      .sage-btn--danger:not([disabled]):not([aria-disabled="true"]):hover {
        filter: brightness(1.1);
      }
      .sage-btn--ghost:not([disabled]):not([aria-disabled="true"]):hover {
        background-color: var(--sage-accent-light);
      }
    `;
    document.head.appendChild(el);
  }
}

const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
  sm: { fontSize: '0.75rem', padding: '0.25rem 0.625rem', gap: '0.25rem' },
  md: { fontSize: '0.875rem', padding: '0.5rem 1rem', gap: '0.375rem' },
  lg: { fontSize: '1rem', padding: '0.625rem 1.25rem', gap: '0.5rem' },
};

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    backgroundColor: 'var(--sage-accent)',
    color: 'var(--sage-accent-text)',
    border: '1px solid transparent',
  },
  secondary: {
    backgroundColor: 'transparent',
    color: 'var(--sage-accent)',
    border: '1px solid var(--sage-accent)',
  },
  danger: {
    backgroundColor: 'var(--sage-risk-destructive-fg)',
    color: 'var(--sage-accent-text)',
    border: '1px solid transparent',
  },
  ghost: {
    backgroundColor: 'transparent',
    color: 'var(--sage-rail-text)',
    border: '1px solid transparent',
  },
};

const Spinner: React.FC<{ size: ButtonSize }> = ({ size }) => {
  const dim = size === 'sm' ? 12 : size === 'lg' ? 18 : 14;
  return (
    <svg
      aria-hidden="true"
      width={dim}
      height={dim}
      viewBox="0 0 16 16"
      fill="none"
      style={{ flexShrink: 0, animation: 'sage-btn-spin 0.75s linear infinite' }}
    >
      <circle
        cx="8"
        cy="8"
        r="6"
        stroke="currentColor"
        strokeOpacity="0.3"
        strokeWidth="2.5"
      />
      <path
        d="M8 2a6 6 0 0 1 6 6"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      disabled = false,
      children,
      style,
      className,
      type = 'button',
      ...rest
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    const baseStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: '0.375rem',
      fontWeight: 500,
      lineHeight: 1.25,
      cursor: isDisabled ? 'not-allowed' : 'pointer',
      opacity: isDisabled ? 0.55 : 1,
      transition:
        'background-color 0.15s ease, border-color 0.15s ease, opacity 0.15s ease, filter 0.15s ease',
      whiteSpace: 'nowrap',
      userSelect: 'none',
      ...variantStyles[variant],
      ...sizeStyles[size],
      ...style,
    };

    return (
      <button
        ref={ref}
        type={type}
        className={`sage-btn sage-btn--${variant}${className ? ` ${className}` : ''}`}
        style={baseStyle}
        disabled={isDisabled}
        aria-disabled={isDisabled ? 'true' : undefined}
        aria-busy={loading ? 'true' : undefined}
        {...rest}
      >
        {loading && <Spinner size={size} />}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button };
export type { ButtonProps, ButtonVariant, ButtonSize };
