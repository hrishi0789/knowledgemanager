import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '../api/endpoints';
import { useUploadStore } from '../stores/uploadStore';

export const useDocuments = (params?: { page?: number; pageSize?: number; status?: string; category?: string }) => {
  return useQuery({
    queryKey: ['documents', params],
    queryFn: () => documentsApi.list(params),
    refetchInterval: (query) => {
      // If there are any documents not yet in terminal state, we poll frequently
      const items = query.state.data?.items || [];
      const hasPending = items.some(
        (d) => d.status !== 'INDEXED' && d.status !== 'FAILED'
      );
      return hasPending ? 3000 : false;
    },
  });
};

export const useDocument = (id: string) => {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsApi.get(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && status !== 'INDEXED' && status !== 'FAILED' ? 2000 : false;
    }
  });
};

export const useUploadDocument = () => {
  const queryClient = useQueryClient();
  const { updateItemProgress, updateItemStatus } = useUploadStore();

  return useMutation({
    mutationFn: async ({ id, file }: { id: string; file: File }) => {
      updateItemStatus(id, 'UPLOADING');
      return documentsApi.upload(file, (pct) => {
        updateItemProgress(id, pct);
      });
    },
    onSuccess: (_, variables) => {
      updateItemStatus(variables.id, 'UPLOADED');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (error, variables) => {
      updateItemStatus(variables.id, 'ERROR', error.message || 'Upload failed');
    },
  });
};

export const useDeleteDocument = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['graph-overview'] });
    },
  });
};

export const useCorrectCategory = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, category }: { id: string; category: string }) =>
      documentsApi.correctCategory(id, category),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['document', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
};
