import { useQuery } from '@tanstack/react-query';
import { graphApi } from '../api/endpoints';

export const useGraphOverview = () => {
  return useQuery({
    queryKey: ['graph-overview'],
    queryFn: () => graphApi.overview(),
  });
};

export const useGraphNeighbors = (nodeKey: string | null, depth: number = 1) => {
  return useQuery({
    queryKey: ['graph-neighbors', nodeKey, depth],
    queryFn: () => graphApi.neighbors(nodeKey!, depth),
    enabled: !!nodeKey,
  });
};
