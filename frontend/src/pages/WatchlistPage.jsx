import { useState } from "react";
import { useWatchlist } from "../hooks/useWatchlist";
import WatchlistTable from "../components/WatchlistTable";
import AddTickerForm from "../components/AddTickerForm";

const TABS = [
  { key: null, label: "All" },
  { key: "watching", label: "Watching" },
  { key: "position_open", label: "Open" },
  { key: "closed", label: "Closed" },
];

export default function WatchlistPage() {
  const [activeTab, setActiveTab] = useState(null);
  const { data: items, isLoading, error } = useWatchlist(activeTab);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink">Watchlist</h1>
        <AddTickerForm />
      </div>

      <div className="flex gap-1 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.key ?? "all"}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 transition-all ${
              activeTab === tab.key
                ? "bg-warm-white border-ink text-ink"
                : "border-transparent text-mid-brown hover:border-ink hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-warm-white border-2 border-ink shadow-hard">
        {isLoading ? (
          <div className="py-16 text-center text-mid-brown font-sans">
            Loading...
          </div>
        ) : error ? (
          <div className="py-16 text-center text-error font-sans">
            Error: {error.message}
          </div>
        ) : (
          <WatchlistTable items={items || []} />
        )}
      </div>
    </div>
  );
}
