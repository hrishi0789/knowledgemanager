import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({ padding = 'md', className = '', style, children, ...props }) => {
  const paddings = {
    none: '0',
    sm: 'var(--s-3)',
    md: 'var(--s-5)',
    lg: 'var(--s-8)',
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--color-surface)',
        borderRadius: 'var(--r-lg)',
        border: '1px solid var(--color-border)',
        padding: paddings[padding],
        overflow: 'hidden',
        ...style,
      }}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
};
