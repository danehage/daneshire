# CLAUDE.md — Frontend

## Context

React 18 SPA with Vite, Tailwind CSS, React Router, and TanStack Query. Communicates with FastAPI backend at `/api/`.

## Key patterns

### API client layer

All API calls go through `src/api/`. Components never call `fetch` directly.

```javascript
// src/api/watchlist.js
const API_BASE = import.meta.env.VITE_API_URL || '';

export async function getWatchlist(status) {
  const params = status ? `?status=${status}` : '';
  const res = await fetch(`${API_BASE}/api/watchlist${params}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export async function createWatchlistItem(data) {
  const res = await fetch(`${API_BASE}/api/watchlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
```

### TanStack Query for server state

Never do `useEffect` + `useState` + `fetch`. Always use `useQuery` and `useMutation`.

```javascript
// src/hooks/useWatchlist.js
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getWatchlist, createWatchlistItem } from '../api/watchlist';

export function useWatchlist(status) {
  return useQuery({
    queryKey: ['watchlist', status],
    queryFn: () => getWatchlist(status),
  });
}

export function useCreateWatchlistItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWatchlistItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });
}
```

### SSE for scan progress

```javascript
// src/hooks/useScanProgress.js
export function useScanProgress(scanId) {
  const [progress, setProgress] = useState(null);

  useEffect(() => {
    if (!scanId) return;
    const source = new EventSource(`/api/scan/${scanId}/stream`);
    source.onmessage = (e) => setProgress(JSON.parse(e.data));
    source.onerror = () => source.close();
    return () => source.close();
  }, [scanId]);

  return progress;
}
```

## Routing

```javascript
// src/App.jsx
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/watchlist" element={<WatchlistPage />} />
  <Route path="/scanner" element={<ScannerPage />} />
  <Route path="/ticker/:symbol" element={<TickerDetailPage />} />
  <Route path="/alerts" element={<AlertsPage />} />
</Routes>
```

## Component conventions

- Page components live in `src/pages/` — one per route
- Reusable components in `src/components/` — organized flat, not nested folders
- Component names match filenames: `WatchlistRow.jsx` exports `WatchlistRow`
- Props destructured in function signature: `function TickerCard({ ticker, price, trend })`
- No prop drilling beyond 2 levels — use context or composition instead

## Styling

- Tailwind utility classes only. No CSS modules, styled-components, or component libraries.
- Dark mode: use `dark:` variants. Detect system preference with Tailwind's `darkMode: 'class'` strategy.
- Color palette: keep it tight. One accent color (blue-500), success (green), warning (amber), danger (red). Backgrounds in gray/slate.
- Consistent spacing: use Tailwind's spacing scale (p-4, gap-3, etc.), don't use arbitrary values.
- Tables: use `<table>` with Tailwind, not a grid of divs.

## Key libraries

```json
{
  "react": "^18.3",
  "react-dom": "^18.3",
  "react-router-dom": "^6.28",
  "@tanstack/react-query": "^5.62",
  "@dnd-kit/core": "^6.3",
  "@dnd-kit/sortable": "^10.0",
  "react-markdown": "^9.0",
  "recharts": "^2.15"
}
```

- `@dnd-kit` for watchlist drag-and-drop reordering
- `react-markdown` for rendering journal entries
- `recharts` for any charts (price history, scanner score distribution)
- Do NOT add: MUI, Chakra, Ant Design, Radix, shadcn. Tailwind handles everything.

## Dev server

Vite dev server runs on `:5173` and proxies `/api` to the backend at `:8000`:

```javascript
// vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```
