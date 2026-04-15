import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getJournalEntries,
  createJournalEntry,
  updateJournalEntry,
  deleteJournalEntry,
  searchJournal,
  getAllJournalEntries,
  createStandaloneJournalEntry,
} from "../api/journal";

export function useJournalEntries(watchlistId) {
  return useQuery({
    queryKey: ["journal", watchlistId],
    queryFn: () => getJournalEntries(watchlistId),
    enabled: !!watchlistId,
  });
}

export function useCreateJournalEntry(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => createJournalEntry(watchlistId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["journal", watchlistId] }),
  });
}

export function useUpdateJournalEntry(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, data }) => updateJournalEntry(entryId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["journal", watchlistId] }),
  });
}

export function useDeleteJournalEntry(watchlistId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId) => deleteJournalEntry(entryId),
    onSuccess: () => {
      // Invalidate specific watchlist journal if provided
      if (watchlistId) {
        queryClient.invalidateQueries({ queryKey: ["journal", watchlistId] });
      }
      // Always invalidate all-journal and search queries
      queryClient.invalidateQueries({ queryKey: ["journal-all"] });
      queryClient.invalidateQueries({ queryKey: ["journal-search"] });
    },
  });
}

export function useJournalSearch(query, entryType = null) {
  return useQuery({
    queryKey: ["journal-search", query, entryType],
    queryFn: () => searchJournal(query, entryType),
    enabled: query?.length >= 2,
    staleTime: 30000, // Cache results for 30 seconds
  });
}

export function useAllJournalEntries(ticker = null, entryType = null) {
  return useQuery({
    queryKey: ["journal-all", ticker, entryType],
    queryFn: () => getAllJournalEntries(ticker, entryType),
  });
}

export function useCreateStandaloneJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createStandaloneJournalEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["journal-all"] });
      queryClient.invalidateQueries({ queryKey: ["journal-search"] });
    },
  });
}
