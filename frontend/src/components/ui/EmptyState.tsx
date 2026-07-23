import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--s-8)',
      textAlign: 'center',
      color: 'var(--color-text-secondary)',
      height: '100%'
    }}>
      {icon && <div style={{ marginBottom: 'var(--s-4)', color: 'var(--color-text-muted)' }}>{icon}</div>}
      <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--s-2)' }}>{title}</h3>
      {description && <p style={{ maxWidth: '400px', marginBottom: 'var(--s-4)' }}>{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
};
