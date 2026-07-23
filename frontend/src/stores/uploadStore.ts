import { create } from 'zustand';

export interface UploadItem {
  id: string; // client-generated temp id
  file: File;
  progress: number;
  status: 'QUEUED' | 'UPLOADING' | 'UPLOADED' | 'ERROR';
  error?: string;
}

interface UploadState {
  queue: UploadItem[];
  addItems: (files: File[]) => void;
  updateItemProgress: (id: string, progress: number) => void;
  updateItemStatus: (id: string, status: UploadItem['status'], error?: string) => void;
  removeItem: (id: string) => void;
  clearCompleted: () => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  queue: [],
  addItems: (files) => {
    const newItems: UploadItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      progress: 0,
      status: 'QUEUED',
    }));
    set((state) => ({ queue: [...state.queue, ...newItems] }));
  },
  updateItemProgress: (id, progress) =>
    set((state) => ({
      queue: state.queue.map((item) =>
        item.id === id ? { ...item, progress } : item
      ),
    })),
  updateItemStatus: (id, status, error) =>
    set((state) => ({
      queue: state.queue.map((item) =>
        item.id === id ? { ...item, status, error } : item
      ),
    })),
  removeItem: (id) =>
    set((state) => ({
      queue: state.queue.filter((item) => item.id !== id),
    })),
  clearCompleted: () =>
    set((state) => ({
      queue: state.queue.filter(
        (item) => item.status !== 'UPLOADED' && item.status !== 'ERROR'
      ),
    })),
}));
