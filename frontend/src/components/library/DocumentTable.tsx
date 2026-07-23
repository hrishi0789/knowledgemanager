import React from 'react';
import { useDocuments, useDeleteDocument } from '../../hooks/useDocuments';
import { Card, Badge, Spinner, EmptyState, Button } from '../ui';
import { FileText, Trash2, ExternalLink } from 'lucide-react';
import type { DocumentStatus, Document } from '../../api/types';

export const DocumentTable: React.FC = () => {
  const { data, isLoading, isError } = useDocuments();
  const deleteDoc = useDeleteDocument();

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--s-8)' }}><Spinner /></div>;
  }

  if (isError) {
    return <div style={{ color: 'var(--color-error)', padding: 'var(--s-4)' }}>Failed to load documents.</div>;
  }

  const items = data?.items || [];

  if (items.length === 0) {
    return (
      <Card padding="none" style={{ height: '300px' }}>
        <EmptyState 
          icon={<FileText size={48} />}
          title="No documents yet"
          description="Upload your first document to start building the knowledge graph."
        />
      </Card>
    );
  }

  const getStatusBadge = (status: DocumentStatus) => {
    switch (status) {
      case 'INDEXED': return <Badge variant="success">Indexed</Badge>;
      case 'FAILED': return <Badge variant="error">Failed</Badge>;
      case 'UPLOADED':
      case 'EXTRACTING':
      case 'EXTRACTED':
      case 'CHUNKED':
        return <Badge variant="info">Processing...</Badge>;
      default: return <Badge>{status}</Badge>;
    }
  };

  return (
    <Card padding="none">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-surface-2)' }}>
              <th style={{ padding: 'var(--s-3) var(--s-4)', fontWeight: 500, color: 'var(--color-text-secondary)' }}>Title</th>
              <th style={{ padding: 'var(--s-3) var(--s-4)', fontWeight: 500, color: 'var(--color-text-secondary)' }}>Category</th>
              <th style={{ padding: 'var(--s-3) var(--s-4)', fontWeight: 500, color: 'var(--color-text-secondary)' }}>Status</th>
              <th style={{ padding: 'var(--s-3) var(--s-4)', fontWeight: 500, color: 'var(--color-text-secondary)' }}>Date</th>
              <th style={{ padding: 'var(--s-3) var(--s-4)', fontWeight: 500, color: 'var(--color-text-secondary)', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((doc: Document) => (
              <tr key={doc.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td style={{ padding: 'var(--s-3) var(--s-4)', display: 'flex', alignItems: 'center', gap: 'var(--s-2)' }}>
                  <FileText size={16} color="var(--color-text-muted)" />
                  <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{doc.title}</span>
                </td>
                <td style={{ padding: 'var(--s-3) var(--s-4)', color: 'var(--color-text-secondary)' }}>
                  {doc.category || '-'}
                </td>
                <td style={{ padding: 'var(--s-3) var(--s-4)' }}>
                  {getStatusBadge(doc.status)}
                </td>
                <td style={{ padding: 'var(--s-3) var(--s-4)', color: 'var(--color-text-secondary)' }}>
                  {new Date(doc.createdAt).toLocaleDateString()}
                </td>
                <td style={{ padding: 'var(--s-3) var(--s-4)', textAlign: 'right' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--s-2)' }}>
                    <Button variant="ghost" size="sm" title="View details (Coming soon)">
                      <ExternalLink size={16} />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => {
                        if (confirm('Delete this document?')) {
                          deleteDoc.mutate(doc.id);
                        }
                      }}
                      title="Delete document"
                      style={{ color: 'var(--color-error)' }}
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
