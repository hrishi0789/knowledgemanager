import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'default';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'default', children, style, ...props }) => {
  const variants: Record<BadgeVariant, React.CSSProperties> = {
    success: { backgroundColor: 'var(--color-success)', color: 'white' },
    warning: { backgroundColor: 'var(--color-warning)', color: 'black' },
    error: { backgroundColor: 'var(--color-error)', color: 'white' },
    info: { backgroundColor: 'var(--color-accent)', color: 'white' },
    default: { backgroundColor: 'var(--color-surface-3)', color: 'var(--color-text-secondary)' },
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px var(--s-2)',
        borderRadius: 'var(--r-sm)',
        fontSize: '0.75rem',
        fontWeight: 600,
        ...variants[variant],
        ...style,
      }}
      {...props}
    >
      {children}
    </span>
  );
};
