import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';

// Lazy load pages for performance
const LibraryPage = React.lazy(() => import('./LibraryPage'));
const SearchPage = React.lazy(() => import('./SearchPage'));
const GraphExplorerPage = React.lazy(() => import('./GraphExplorerPage'));
const AnalyticsPage = React.lazy(() => import('./AnalyticsPage'));
const AdminPage = React.lazy(() => import('./AdminPage'));

const SuspenseWrapper = ({ children }: { children: React.ReactNode }) => (
  <React.Suspense fallback={<div style={{ padding: 'var(--s-8)', textAlign: 'center' }}>Loading...</div>}>
    {children}
  </React.Suspense>
);

export const AppRouter = () => {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Navigate to="/library" replace />} />
        <Route path="library" element={<SuspenseWrapper><LibraryPage /></SuspenseWrapper>} />
        <Route path="search" element={<SuspenseWrapper><SearchPage /></SuspenseWrapper>} />
        <Route path="graph" element={<SuspenseWrapper><GraphExplorerPage /></SuspenseWrapper>} />
        <Route path="analytics" element={<SuspenseWrapper><AnalyticsPage /></SuspenseWrapper>} />
        <Route path="admin" element={<SuspenseWrapper><AdminPage /></SuspenseWrapper>} />
      </Route>
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
};
