import { useQuery } from "@tanstack/react-query";
import { analyzeTicker } from "../api/scanner";
import { getWatchlist } from "../api/watchlist";

export function useTickerAnalysis(symbol) {
  return useQuery({
    queryKey: ["ticker", symbol],
    queryFn: () => analyzeTicker(symbol),
    enabled: !!symbol,
    staleTime: 60 * 1000, // 1 minute - quotes don't need constant refresh
  });
}

export function useTickerWatchlistItem(symbol) {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => getWatchlist(),
    select: (data) => data.find((item) => item.ticker === symbol?.toUpperCase()),
    enabled: !!symbol,
  });
}
