import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', fullWidth = false, className = '', children, ...props }, ref) => {
    
    const baseStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontWeight: 500,
      borderRadius: 'var(--r-md)',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      border: 'none',
      width: fullWidth ? '100%' : 'auto',
      fontFamily: 'inherit',
    };

    const variants: Record<string, React.CSSProperties> = {
      primary: {
        backgroundColor: 'var(--color-primary)',
        color: 'var(--color-bg)',
      },
      secondary: {
        backgroundColor: 'var(--color-surface-3)',
        color: 'var(--color-text-primary)',
        border: '1px solid var(--color-border)',
      },
      danger: {
        backgroundColor: 'var(--color-error)',
        color: 'white',
      },
      ghost: {
        backgroundColor: 'transparent',
        color: 'var(--color-text-secondary)',
      },
    };

    const sizes: Record<string, React.CSSProperties> = {
      sm: { padding: 'var(--s-2) var(--s-3)', fontSize: '0.875rem' },
      md: { padding: 'var(--s-3) var(--s-4)', fontSize: '1rem' },
      lg: { padding: 'var(--s-4) var(--s-6)', fontSize: '1.125rem' },
    };

    return (
      <button
        ref={ref}
        style={{ ...baseStyle, ...variants[variant], ...sizes[size], ...(props.disabled ? { opacity: 0.5, cursor: 'not-allowed' } : {}) }}
        className={className}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
