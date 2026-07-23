import React, { useState } from 'react';
import { Search as SearchIcon, FileText, Network } from 'lucide-react';
import { useSearchStore } from '../../stores/searchStore';
import { Input, Button } from '../ui';

export const SearchBar: React.FC = () => {
  const { mode, lastQuery, setMode, setQuery } = useSearchStore();
  const [localQuery, setLocalQuery] = useState(lastQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (localQuery.trim()) {
      setQuery(localQuery.trim());
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-4)' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 'var(--s-3)' }}>
        <Input 
          placeholder="Search knowledge base..." 
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          style={{ flex: 1 }}
        />
        <Button type="submit" size="lg">
          <SearchIcon size={20} style={{ marginRight: 'var(--s-2)' }} />
          Search
        </Button>
      </form>
      <div style={{ display: 'flex', gap: 'var(--s-3)' }}>
        <Button 
          variant={mode === 'semantic' ? 'primary' : 'secondary'} 
          size="sm"
          onClick={() => setMode('semantic')}
        >
          <FileText size={16} style={{ marginRight: 'var(--s-2)' }} />
          Semantic
        </Button>
        <Button 
          variant={mode === 'graph' ? 'primary' : 'secondary'} 
          size="sm"
          onClick={() => setMode('graph')}
        >
          <Network size={16} style={{ marginRight: 'var(--s-2)' }} />
          Graph Multi-hop
        </Button>
      </div>
    </div>
  );
};
