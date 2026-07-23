import { create } from 'zustand';

interface UiState {
  sidebarOpen: boolean;
  theme: 'dark' | 'light';
  graphLayoutName: string;
  selectedNodeKey: string | null;
  toggleSidebar: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
  setGraphLayout: (layout: string) => void;
  setSelectedNodeKey: (key: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  theme: 'dark', // Defaulting to dark as per index.css
  graphLayoutName: 'cose-bilkent',
  selectedNodeKey: null,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
  setGraphLayout: (graphLayoutName) => set({ graphLayoutName }),
  setSelectedNodeKey: (selectedNodeKey) => set({ selectedNodeKey }),
}));
