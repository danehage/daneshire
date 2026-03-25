import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAlerts,
  getAlert,
  createAlert,
  updateAlert,
  deleteAlert,
  dismissAlert,
  getAlertHistory,
} from "../api/alerts";

export function useAlerts(status, ticker) {
  return useQuery({
    queryKey: ["alerts", status, ticker],
    queryFn: () => getAlerts(status, ticker),
  });
}

export function useAlert(id) {
  return useQuery({
    queryKey: ["alert", id],
    queryFn: () => getAlert(id),
    enabled: !!id,
  });
}

export function useCreateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => updateAlert(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useAlertHistory(id) {
  return useQuery({
    queryKey: ["alertHistory", id],
    queryFn: () => getAlertHistory(id),
    enabled: !!id,
  });
}
