import React from 'react';
import { UploadDropzone } from '../components/library/UploadDropzone';
import { DocumentTable } from '../components/library/DocumentTable';

const LibraryPage: React.FC = () => {
  return (
    <div style={{ padding: 'var(--s-6)', maxWidth: '1200px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--s-8)' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: 'var(--s-2)' }}>Library</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>Upload and manage your documents for the knowledge graph.</p>
      </div>

      <UploadDropzone />
      
      <div>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 'var(--s-4)' }}>Documents</h2>
        <DocumentTable />
      </div>
    </div>
  );
};

export default LibraryPage;
