import React from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { SearchResults } from '../components/search/SearchResults';
import { GraphResultPanel } from '../components/search/GraphResultPanel';
import { useSearchStore } from '../stores/searchStore';

const SearchPage: React.FC = () => {
  const { mode } = useSearchStore();

  return (
    <div style={{ padding: 'var(--s-6)', maxWidth: '1400px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--s-6)', height: '100%' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: 'var(--s-2)' }}>Search</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>Find information semantically or explore multi-hop graph paths.</p>
      </div>

      <SearchBar />

      <div style={{ display: 'flex', gap: 'var(--s-6)', flex: 1, minHeight: 0 }}>
        <div style={{ flex: mode === 'graph' ? '0 0 45%' : '1', overflowY: 'auto', paddingRight: 'var(--s-2)' }}>
          <SearchResults />
        </div>
        
        {mode === 'graph' && (
          <div style={{ flex: '1', display: 'flex', flexDirection: 'column' }}>
            <GraphResultPanel />
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
