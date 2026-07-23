import React from 'react';
import { useUiStore } from '../../stores/uiStore';
import { Button } from '../ui';
import { LayoutDashboard, Moon, Sun } from 'lucide-react';

export const GraphToolbar: React.FC = () => {
  const { theme, setTheme, graphLayoutName, setGraphLayout } = useUiStore();

  const layouts = ['cose-bilkent', 'concentric', 'grid', 'circle'];

  return (
    <div style={{ display: 'flex', gap: 'var(--s-4)', padding: 'var(--s-3)', backgroundColor: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-2)' }}>
        <LayoutDashboard size={18} color="var(--color-text-secondary)" />
        <select 
          value={graphLayoutName} 
          onChange={(e) => setGraphLayout(e.target.value)}
          style={{ 
            backgroundColor: 'var(--color-surface-2)', 
            color: 'var(--color-text-primary)', 
            border: '1px solid var(--color-border)', 
            padding: 'var(--s-1) var(--s-2)', 
            borderRadius: 'var(--r-sm)',
            outline: 'none'
          }}
        >
          {layouts.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>

      <div style={{ flex: 1 }} />

      <Button variant="ghost" size="sm" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </Button>
    </div>
  );
};
