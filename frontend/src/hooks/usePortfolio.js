import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAccounts, getPortfolio, commitSnapshot } from "../api/portfolio";

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
