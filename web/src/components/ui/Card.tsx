import React, { forwardRef } from 'react';

// Card — a neutral surface container. Follows the ui/ primitive convention
// (Button.tsx, RiskBadge.tsx): inline React.CSSProperties consuming --sage-*
// design tokens, forwardRef, displayName. No hardcoded hex, no extra deps.

type CardVariant = 'default' | 'muted' | 'outlined';
type CardPadding = 'none' | 'sm' | 'md' | 'lg';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  padding?: CardPadding;
}

const paddingStyles: Record<CardPadding, React.CSSProperties> = {
  none: { padding: 0 },
  sm: { padding: '0.75rem' },
  md: { padding: '1rem' },
  lg: { padding: '1.5rem' },
};

const variantStyles: Record<CardVariant, React.CSSProperties> = {
  default: { backgroundColor: 'var(--sage-surface)', border: '1px solid var(--sage-border)' },
  muted: { backgroundColor: 'var(--sage-surface-muted)', border: '1px solid var(--sage-border)' },
  outlined: { backgroundColor: 'transparent', border: '1px solid var(--sage-border)' },
};

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = 'default', padding = 'md', style, className, children, ...rest }, ref) => {
    const baseStyle: React.CSSProperties = {
      borderRadius: '0.5rem',
      color: 'var(--sage-text)',
      ...variantStyles[variant],
      ...paddingStyles[padding],
      ...style,
    };
    return (
      <div ref={ref} className={className} style={baseStyle} {...rest}>
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export { Card };
export type { CardProps, CardVariant, CardPadding };
