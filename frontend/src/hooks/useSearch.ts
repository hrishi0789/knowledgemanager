import { useQuery } from '@tanstack/react-query';
import { searchApi } from '../api/endpoints';

export const useSemanticSearch = (query: string, topK: number = 10, category?: string) => {
  return useQuery({
    queryKey: ['search-semantic', query, topK, category],
    queryFn: () => searchApi.semantic(query, topK, category),
    enabled: !!query,
  });
};

export const useGraphSearch = (
  query: string,
  opts?: { hops?: number; decay?: number; gateThreshold?: number; topKSeeds?: number }
) => {
  return useQuery({
    queryKey: ['search-graph', query, opts],
    queryFn: () => searchApi.graph(query, opts),
    enabled: !!query,
  });
};
