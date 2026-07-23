import { create } from 'zustand';

export type SearchMode = 'semantic' | 'graph';

interface SearchFilters {
  category: string | null;
}

interface SearchState {
  mode: SearchMode;
  lastQuery: string;
  filters: SearchFilters;
  setMode: (mode: SearchMode) => void;
  setQuery: (query: string) => void;
  setFilterCategory: (category: string | null) => void;
  resetFilters: () => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  mode: 'semantic',
  lastQuery: '',
  filters: { category: null },
  setMode: (mode) => set({ mode }),
  setQuery: (lastQuery) => set({ lastQuery }),
  setFilterCategory: (category) =>
    set((state) => ({ filters: { ...state.filters, category } })),
  resetFilters: () => set({ filters: { category: null } }),
}));
