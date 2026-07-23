import React, { useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, File as FileIcon, XCircle, CheckCircle, Loader2 } from 'lucide-react';
import { useUploadStore } from '../../stores/uploadStore';
import { useUploadDocument } from '../../hooks/useDocuments';
import { Card } from '../ui';

export const UploadDropzone: React.FC = () => {
  const { queue, addItems, clearCompleted, removeItem } = useUploadStore();
  const uploadDoc = useUploadDocument();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    addItems(acceptedFiles);
  }, [addItems]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  // Automatically start uploads for QUEUED items
  useEffect(() => {
    queue.forEach(item => {
      if (item.status === 'QUEUED') {
        uploadDoc.mutate({ id: item.id, file: item.file });
      }
    });
  }, [queue, uploadDoc]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-4)' }}>
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? 'var(--color-primary)' : 'var(--color-border)'}`,
          borderRadius: 'var(--r-lg)',
          padding: 'var(--s-8)',
          textAlign: 'center',
          backgroundColor: isDragActive ? 'var(--color-surface-3)' : 'var(--color-surface)',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
      >
        <input {...getInputProps()} />
        <UploadCloud size={48} color={isDragActive ? 'var(--color-primary)' : 'var(--color-text-muted)'} style={{ marginBottom: 'var(--s-4)' }} />
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '1.125rem' }}>
          {isDragActive ? "Drop files here..." : "Drag & drop files here, or click to select"}
        </p>
      </div>

      {queue.length > 0 && (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--s-4)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Upload Queue</h3>
            <button 
              onClick={clearCompleted}
              style={{ background: 'none', border: 'none', color: 'var(--color-primary)', cursor: 'pointer', fontSize: '0.875rem' }}
            >
              Clear Completed
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--s-3)' }}>
            {queue.map(item => (
              <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-3)', padding: 'var(--s-3)', backgroundColor: 'var(--color-surface-2)', borderRadius: 'var(--r-md)' }}>
                <FileIcon size={20} color="var(--color-text-secondary)" />
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--color-text-primary)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {item.file.name}
                  </div>
                  {item.status === 'UPLOADING' && (
                    <div style={{ width: '100%', backgroundColor: 'var(--color-surface-3)', height: '4px', borderRadius: '2px', marginTop: 'var(--s-2)' }}>
                      <div style={{ width: `${item.progress}%`, backgroundColor: 'var(--color-primary)', height: '100%', borderRadius: '2px', transition: 'width 0.2s' }} />
                    </div>
                  )}
                  {item.status === 'ERROR' && <div style={{ color: 'var(--color-error)', fontSize: '0.75rem', marginTop: 'var(--s-1)' }}>{item.error}</div>}
                </div>
                <div>
                  {item.status === 'UPLOADING' && <Loader2 size={16} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />}
                  {item.status === 'UPLOADED' && <CheckCircle size={16} color="var(--color-success)" />}
                  {item.status === 'ERROR' && <XCircle size={16} color="var(--color-error)" />}
                </div>
                <button 
                  onClick={() => removeItem(item.id)}
                  style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', display: 'flex' }}
                >
                  <XCircle size={16} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}
      <style>
        {`@keyframes spin { to { transform: rotate(360deg); } }`}
      </style>
    </div>
  );
};
