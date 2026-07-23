import React from 'react';
import { Card, Badge, Spinner, EmptyState } from '../ui';
import { SearchHit } from '../../api/types';
import { useSearchStore } from '../../stores/searchStore';
import { useSemanticSearch, useGraphSearch } from '../../hooks/useSearch';
import { FileText, AlertTriangle } from 'lucide-react';

export const SearchResults: React.FC = () => {
  const { mode, lastQuery, filters } = useSearchStore();

  const semanticSearch = useSemanticSearch(mode === 'semantic' ? lastQuery : '', 10, filters.category || undefined);
  const graphSearch = useGraphSearch(mode === 'graph' ? lastQuery : '');

  if (!lastQuery) {
    return (
      <EmptyState 
        icon={<FileText size={48} />}
        title="Ready to search"
        description="Enter a query above to explore the knowledge base."
      />
    );
  }

  const isLoading = mode === 'semantic' ? semanticSearch.isLoading : graphSearch.isLoading;
  const isError = mode === 'semantic' ? semanticSearch.isError : graphSearch.isError;
  const data = mode === 'semantic' ? semanticSearch.data : graphSearch.data;

  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--s-8)' }}><Spinner /></div>;
  if (isError) return <div style={{ color: 'var(--color-error)' }}>An error occurred while searching.</div>;
  if (!data) return null;

  const hits: SearchHit[] = 'hits' in data ? data.hits : [];
  const degraded = 'degraded' in data ? data.degraded : false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-4)' }}>
      {degraded && (
        <div style={{ padding: 'var(--s-3)', backgroundColor: 'var(--color-warning)', color: 'black', borderRadius: 'var(--r-md)', display: 'flex', alignItems: 'center', gap: 'var(--s-2)' }}>
          <AlertTriangle size={20} />
          <strong>Graph search degraded:</strong> Showing semantic results instead due to backend limitations.
        </div>
      )}

      {hits.length === 0 ? (
        <EmptyState title="No results found" description={`No matches for "${lastQuery}"`} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-4)' }}>
          {hits.map((hit, index) => (
            <Card key={`${hit.documentId}-${hit.chunkId}-${index}`} padding="md">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--s-2)' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
                  {hit.documentTitle}
                </h3>
                <Badge variant="info">Score: {hit.score.toFixed(2)}</Badge>
              </div>
              {hit.category && <Badge style={{ marginBottom: 'var(--s-3)' }}>{hit.category}</Badge>}
              <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                {hit.preview}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
