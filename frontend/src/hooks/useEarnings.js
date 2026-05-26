import { useQuery } from '@tanstack/react-query';
import { getEarningsCalendar } from '../api/earnings';

export function useEarningsCalendar({ start, end } = {}) {
  return useQuery({
    queryKey: ['earnings', 'calendar', start, end],
    queryFn: () => getEarningsCalendar({ start, end }),
  });
}
