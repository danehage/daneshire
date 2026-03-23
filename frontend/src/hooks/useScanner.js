import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getUniverses,
  executeScan,
  getScanResults,
  analyzeTicker,
  createScanStream,
} from "../api/scanner";

export function useUniverses() {
  return useQuery({
    queryKey: ["universes"],
    queryFn: getUniverses,
    staleTime: 1000 * 60 * 60, // 1 hour - universes don't change often
  });
}

export function useAnalyzeTicker(symbol) {
  return useQuery({
    queryKey: ["analyze", symbol],
    queryFn: () => analyzeTicker(symbol),
    enabled: !!symbol,
  });
}

export function useScan() {
  const [scanId, setScanId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState(null);
  const queryClient = useQueryClient();

  // Start scan mutation
  const startScan = useMutation({
    mutationFn: executeScan,
    onSuccess: (data) => {
      setScanId(data.scan_id);
      setIsScanning(true);
      setError(null);
      setProgress({ current: 0, total: data.universe_size, found: 0 });
    },
    onError: (err) => {
      setError(err.message);
      setIsScanning(false);
    },
  });

  // SSE progress tracking
  useEffect(() => {
    if (!scanId || !isScanning) return;

    const eventSource = createScanStream(scanId);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "progress") {
          setProgress({
            current: data.current,
            total: data.total,
            found: data.found,
          });
        } else if (data.type === "complete") {
          setIsScanning(false);
          // Invalidate to fetch results
          queryClient.invalidateQueries({ queryKey: ["scanResults", scanId] });
          eventSource.close();
        } else if (data.type === "error") {
          setError(data.error);
          setIsScanning(false);
          eventSource.close();
        }
      } catch (e) {
        console.error("Failed to parse SSE event:", e);
      }
    };

    eventSource.onerror = () => {
      setError("Connection lost");
      setIsScanning(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [scanId, isScanning, queryClient]);

  // Fetch results when scan is complete
  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ["scanResults", scanId],
    queryFn: () => getScanResults(scanId),
    enabled: !!scanId && !isScanning,
    retry: false,
  });

  const reset = useCallback(() => {
    setScanId(null);
    setProgress(null);
    setIsScanning(false);
    setError(null);
  }, []);

  return {
    startScan: startScan.mutate,
    isStarting: startScan.isPending,
    scanId,
    progress,
    isScanning,
    results,
    resultsLoading,
    error,
    reset,
  };
}
