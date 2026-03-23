import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPriceTargets,
  createPriceTarget,
  updatePriceTarget,
  deletePriceTarget,
} from "../api/priceTargets";

export function usePriceTargets(watchlistId) {
  return useQuery({
    queryKey: ["priceTargets", watchlistId],
    queryFn: () => getPriceTargets(watchlistId),
    enabled: !!watchlistId,
  });
}

export function useCreatePriceTarget(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => createPriceTarget(watchlistId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["priceTargets", watchlistId] }),
  });
}

export function useUpdatePriceTarget(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetId, data }) =>
      updatePriceTarget(watchlistId, targetId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["priceTargets", watchlistId] }),
  });
}

export function useDeletePriceTarget(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId) => deletePriceTarget(watchlistId, targetId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["priceTargets", watchlistId] }),
  });
}
