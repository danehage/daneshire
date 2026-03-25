import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary } from "../api/dashboard";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    staleTime: 30 * 1000, // 30 seconds
  });
}
