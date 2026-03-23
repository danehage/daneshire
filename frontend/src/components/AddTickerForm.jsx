import { useState } from "react";
import { useCreateWatchlistItem } from "../hooks/useWatchlist";

export default function AddTickerForm() {
  const [ticker, setTicker] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const createItem = useCreateWatchlistItem();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!ticker.trim()) return;

    createItem.mutate(
      { ticker: ticker.trim().toUpperCase() },
      {
        onSuccess: () => {
          setTicker("");
          setIsOpen(false);
        },
      }
    );
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="px-5 py-2.5 bg-accent text-warm-white font-semibold uppercase tracking-wide text-sm border-2 border-ink shadow-hard hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-hard-lg hover:bg-accent-hover active:translate-x-0 active:translate-y-0 active:shadow-hard-sm transition-all"
      >
        + Add Ticker
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        type="text"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder="AAPL"
        autoFocus
        className="px-4 py-2.5 border-2 border-ink bg-warm-white text-ink text-sm w-28 focus:outline-none focus:shadow-hard-sm transition-shadow"
      />
      <button
        type="submit"
        disabled={createItem.isPending}
        className="px-5 py-2.5 bg-accent text-warm-white font-semibold uppercase tracking-wide text-sm border-2 border-ink shadow-hard-sm hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-hard hover:bg-accent-hover active:translate-x-0 active:translate-y-0 active:shadow-none disabled:opacity-50 disabled:transform-none transition-all"
      >
        {createItem.isPending ? "..." : "Add"}
      </button>
      <button
        type="button"
        onClick={() => {
          setIsOpen(false);
          setTicker("");
        }}
        className="px-4 py-2.5 text-mid-brown hover:text-ink text-sm font-medium uppercase tracking-wide border-2 border-transparent hover:border-ink transition-all"
      >
        Cancel
      </button>
    </form>
  );
}
