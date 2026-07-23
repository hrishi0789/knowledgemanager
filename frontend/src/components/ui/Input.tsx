import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-1)', width: '100%' }} className={className}>
        {label && (
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
            {label}
          </label>
        )}
        <input
          ref={ref}
          style={{
            padding: 'var(--s-3)',
            borderRadius: 'var(--r-md)',
            border: `1px solid ${error ? 'var(--color-error)' : 'var(--color-border)'}`,
            backgroundColor: 'var(--color-surface-2)',
            color: 'var(--color-text-primary)',
            fontSize: '1rem',
            outline: 'none',
            fontFamily: 'inherit',
            transition: 'border-color 0.2s',
          }}
          onFocus={(e) => {
            if (!error) e.target.style.borderColor = 'var(--color-primary)';
          }}
          onBlur={(e) => {
            if (!error) e.target.style.borderColor = 'var(--color-border)';
          }}
          {...props}
        />
        {error && <span style={{ fontSize: '0.75rem', color: 'var(--color-error)' }}>{error}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';
