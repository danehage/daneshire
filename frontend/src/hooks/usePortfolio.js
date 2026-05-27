import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAccounts, getPortfolio, commitSnapshot, commitTrade, getTrades } from "../api/portfolio";

export function useAccounts() {
  return useQuery({
    queryKey: ["portfolio", "accounts"],
    queryFn: getAccounts,
  });
}

export function usePortfolio(accountId) {
  return useQuery({
    queryKey: ["portfolio", "holdings", accountId],
    queryFn: () => getPortfolio(accountId),
  });
}

export function useCommitSnapshot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: commitSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useCommitTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: commitTrade,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useTrades(filters) {
  return useQuery({
    queryKey: ["portfolio", "trades", filters],
    queryFn: () => getTrades(filters),
  });
}
