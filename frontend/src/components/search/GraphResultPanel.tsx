import React from 'react';
import { useSearchStore } from '../../stores/searchStore';
import { useGraphSearch } from '../../hooks/useSearch';
import { Card, Spinner } from '../ui';

// This is a simplified mini-view, the full Cytoscape canvas is in GraphExplorerPage
export const GraphResultPanel: React.FC = () => {
  const { mode, lastQuery } = useSearchStore();
  const { data, isLoading } = useGraphSearch(mode === 'graph' ? lastQuery : '');

  if (mode !== 'graph' || !lastQuery) return null;

  return (
    <Card style={{ flex: 1, minHeight: '300px', display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: 'var(--s-4)', color: 'var(--color-text-primary)' }}>
        Activated Subgraph
      </h3>
      <div style={{ flex: 1, backgroundColor: 'var(--color-surface-2)', borderRadius: 'var(--r-md)', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {isLoading ? (
          <Spinner />
        ) : data && 'nodes' in data ? (
          <div style={{ padding: 'var(--s-4)', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
            <p style={{ marginBottom: 'var(--s-2)' }}>Found {data.nodes.length} nodes and {data.edges.length} relationships.</p>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              (Mini-map visualization would render here. See Graph Explorer for full interactive view.)
            </p>
          </div>
        ) : null}
      </div>
    </Card>
  );
};
