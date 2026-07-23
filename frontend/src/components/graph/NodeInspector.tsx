import React from 'react';
import { useGraphNeighbors } from '../../hooks/useGraph';
import { useUiStore } from '../../stores/uiStore';
import { Card, Badge, Spinner } from '../ui';
import { X, Network } from 'lucide-react';

export const NodeInspector: React.FC = () => {
  const { selectedNodeKey, setSelectedNodeKey } = useUiStore();
  const { data, isLoading } = useGraphNeighbors(selectedNodeKey);

  if (!selectedNodeKey) return null;

  return (
    <Card 
      style={{ 
        position: 'absolute', 
        top: 'var(--s-4)', 
        right: 'var(--s-4)', 
        width: '300px', 
        maxHeight: 'calc(100% - var(--s-8))', 
        overflowY: 'auto',
        zIndex: 10,
        boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--s-4)' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Inspector</h3>
        <button 
          onClick={() => setSelectedNodeKey(null)}
          style={{ background: 'none', border: 'none', color: 'var(--color-text-secondary)', cursor: 'pointer', display: 'flex' }}
        >
          <X size={18} />
        </button>
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--s-4)' }}><Spinner size={20} /></div>
      ) : data ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-4)' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--s-2)' }}>
              <strong style={{ fontSize: '1.125rem', color: 'var(--color-primary)' }}>{data.center.name}</strong>
            </div>
            <div style={{ display: 'flex', gap: 'var(--s-2)', flexWrap: 'wrap' }}>
              <Badge>{data.center.label}</Badge>
              {data.center.pagerank !== null && <Badge variant="info">PR: {data.center.pagerank.toFixed(3)}</Badge>}
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 'var(--s-2)', display: 'flex', alignItems: 'center', gap: 'var(--s-1)' }}>
              <Network size={14} /> Neighbors ({data.neighbors.length})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-2)' }}>
              {data.neighbors.map(n => (
                <div 
                  key={n.key} 
                  style={{ padding: 'var(--s-2)', backgroundColor: 'var(--color-surface-2)', borderRadius: 'var(--r-sm)', cursor: 'pointer', transition: 'background-color 0.2s' }}
                  onClick={() => setSelectedNodeKey(n.key)}
                >
                  <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>{n.name}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    <span>{n.label}</span>
                    <span>{n.relationshipType}</span>
                  </div>
                </div>
              ))}
              {data.neighbors.length === 0 && <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>No neighbors found.</span>}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ color: 'var(--color-error)' }}>Failed to load node data.</div>
      )}
    </Card>
  );
};
