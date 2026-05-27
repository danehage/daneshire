import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getEarningsCalendar,
  getEarningsScreen,
  getEarningsExpectedMove,
  getEarningsTrades,
  createEarningsTrade,
  updateEarningsTrade,
  deleteEarningsTrade,
} from '../api/earnings';

export function useEarningsCalendar({ start, end } = {}) {
  return useQuery({
    queryKey: ['earnings', 'calendar', start, end],
    queryFn: () => getEarningsCalendar({ start, end }),
  });
}

export function useEarningsScreen({
  start,
  end,
  minIvRank,
  minEdgeRatio,
  minVolume,
} = {}) {
  return useQuery({
    queryKey: ['earnings', 'screen', start, end, minIvRank, minEdgeRatio, minVolume],
    queryFn: () =>
      getEarningsScreen({ start, end, minIvRank, minEdgeRatio, minVolume }),
  });
}

export function useEarningsExpectedMove(ticker) {
  return useQuery({
    queryKey: ['earnings', 'expectedMove', ticker],
    queryFn: () => getEarningsExpectedMove(ticker),
    enabled: Boolean(ticker),
  });
}

export function useEarningsTrades(filters = {}) {
  return useQuery({
    queryKey: ['earnings', 'trades', filters],
    queryFn: () => getEarningsTrades(filters),
  });
}

export function useCreateEarningsTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createEarningsTrade,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['earnings', 'trades'] }),
  });
}

export function useUpdateEarningsTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }) => updateEarningsTrade(id, patch),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['earnings', 'trades'] }),
  });
}

export function useDeleteEarningsTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteEarningsTrade,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['earnings', 'trades'] }),
  });
}
