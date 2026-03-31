import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDashboardSummary } from "../hooks/useDashboard";
import { useJournalSearch } from "../hooks/useJournal";

const ENTRY_TYPE_COLORS = {
  thesis: "bg-accent text-warm-white",
  note: "bg-light-brown text-warm-white",
  entry: "bg-success text-warm-white",
  exit: "bg-error text-warm-white",
  adjustment: "bg-warning text-warm-white",
  review: "bg-mid-brown text-warm-white",
};

function formatDate(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;

  // Handle clock skew or very recent entries
  if (diffMs < 60000) return "just now";

  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function SummaryCard({ title, value, subtitle, linkTo, linkLabel }) {
  return (
    <div className="border-2 border-ink shadow-hard-sm sm:shadow-hard bg-warm-white p-4 sm:p-6">
      <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
        {title}
      </h3>
      <p className="text-3xl sm:text-4xl font-serif font-bold text-ink mb-1">{value}</p>
      {subtitle && <p className="text-sm text-mid-brown">{subtitle}</p>}
      {linkTo && (
        <Link
          to={linkTo}
          className="inline-block mt-3 text-sm text-accent hover:text-accent-hover font-medium"
        >
          {linkLabel} →
        </Link>
      )}
    </div>
  );
}

function JournalEntryRow({ entry }) {
  const truncatedContent =
    entry.content.length > 120
      ? entry.content.substring(0, 120) + "..."
      : entry.content;

  return (
    <div className="border-b-2 border-ink last:border-b-0 py-4 px-4 hover:bg-cream transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              to={`/ticker/${entry.ticker}`}
              className="font-serif text-lg text-ink hover:text-accent"
            >
              {entry.ticker}
            </Link>
            <span
              className={`text-xs px-2 py-0.5 border border-ink uppercase tracking-wide ${
                ENTRY_TYPE_COLORS[entry.entry_type] || "bg-light-brown text-warm-white"
              }`}
            >
              {entry.entry_type}
            </span>
          </div>
          <p className="text-sm text-mid-brown line-clamp-2">{truncatedContent}</p>
        </div>
        <span className="text-xs text-light-brown whitespace-nowrap">
          {formatDate(entry.created_at)}
        </span>
      </div>
    </div>
  );
}

function JournalSearch() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const containerRef = useRef(null);
  const navigate = useNavigate();

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setQuery("");
        setDebouncedQuery("");
      }
    }
    if (debouncedQuery.length >= 2) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [debouncedQuery]);

  const { data: results, isLoading, error } = useJournalSearch(debouncedQuery);
  const showResults = debouncedQuery.length >= 2;

  function handleResultClick(ticker) {
    setQuery("");
    setDebouncedQuery("");
    navigate(`/ticker/${ticker}`);
  }

  function handleKeyDown(e) {
    if (e.key === "Escape") {
      setQuery("");
      setDebouncedQuery("");
      e.target.blur();
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <div className="border-2 border-ink shadow-hard-sm sm:shadow-hard bg-warm-white">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search journal entries..."
          className="w-full px-3 sm:px-4 py-2 sm:py-3 text-sm sm:text-base bg-transparent text-ink placeholder-light-brown focus:outline-none"
        />
      </div>

      {showResults && (
        <div className="absolute z-10 w-full mt-2 border-2 border-ink shadow-hard bg-warm-white max-h-80 overflow-y-auto">
          {isLoading && (
            <div className="py-4 text-center text-mid-brown">Searching...</div>
          )}
          {error && (
            <div className="py-4 text-center text-error">
              Error: {error.message}
            </div>
          )}
          {results && results.length === 0 && (
            <div className="py-4 text-center text-mid-brown">
              No results found
            </div>
          )}
          {results && results.length > 0 && (
            <>
              <div className="px-4 py-2 text-xs text-light-brown border-b border-ink">
                {results.length} result{results.length !== 1 && "s"}
              </div>
              {results.map((entry) => (
                <div
                  key={entry.id}
                  onClick={() => handleResultClick(entry.ticker)}
                  className="cursor-pointer"
                >
                  <SearchResultRow entry={entry} />
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SearchResultRow({ entry }) {
  const truncatedContent =
    entry.content.length > 120
      ? entry.content.substring(0, 120) + "..."
      : entry.content;

  return (
    <div className="border-b-2 border-ink last:border-b-0 py-4 px-4 hover:bg-cream transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-serif text-lg text-ink hover:text-accent">
              {entry.ticker}
            </span>
            <span
              className={`text-xs px-2 py-0.5 border border-ink uppercase tracking-wide ${
                ENTRY_TYPE_COLORS[entry.entry_type] || "bg-light-brown text-warm-white"
              }`}
            >
              {entry.entry_type}
            </span>
          </div>
          <p className="text-sm text-mid-brown line-clamp-2">{truncatedContent}</p>
        </div>
        <span className="text-xs text-light-brown whitespace-nowrap">
          {formatDate(entry.created_at)}
        </span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardSummary();

  if (isLoading) {
    return (
      <div className="py-12 text-center text-mid-brown">Loading dashboard...</div>
    );
  }

  if (error) {
    return (
      <div className="border-2 border-error bg-error/10 p-4 text-error">
        Error loading dashboard: {error.message}
      </div>
    );
  }

  const { watchlist, alerts, recent_journal } = data;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="font-serif text-3xl sm:text-4xl mb-2">
            <span className="text-accent">Dane</span>
            <span className="text-ink">shire Hathaway</span>
          </h1>
          <p className="text-mid-brown text-sm sm:text-base">
            Stock research terminal for swing trading and options strategies.
          </p>
        </div>
        <div className="w-full max-w-md">
          <JournalSearch />
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="Watching"
          value={watchlist.watching}
          subtitle={`${watchlist.total} total tickers`}
          linkTo="/watchlist"
          linkLabel="View watchlist"
        />
        <SummaryCard
          title="Open Positions"
          value={watchlist.open}
          subtitle={`${watchlist.closed} closed`}
          linkTo="/watchlist"
          linkLabel="Manage positions"
        />
        <SummaryCard
          title="Active Alerts"
          value={alerts.active}
          subtitle={`${alerts.triggered_today} triggered today`}
          linkTo="/alerts"
          linkLabel="View alerts"
        />
        <SummaryCard
          title="Scanner"
          value="—"
          subtitle="Find opportunities"
          linkTo="/scanner"
          linkLabel="Run scan"
        />
      </div>

      {/* Recent Journal Entries */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-2xl text-ink">Recent Activity</h2>
          <Link
            to="/watchlist"
            className="text-sm text-accent hover:text-accent-hover font-medium"
          >
            View all →
          </Link>
        </div>

        <div className="border-2 border-ink shadow-hard bg-warm-white">
          {recent_journal.length === 0 ? (
            <div className="py-12 text-center text-mid-brown">
              No journal entries yet. Add some notes to your watchlist items!
            </div>
          ) : (
            recent_journal.map((entry) => (
              <JournalEntryRow key={entry.id} entry={entry} />
            ))
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          to="/scanner"
          className="border-2 border-ink shadow-hard bg-warm-white p-6 hover:bg-cream transition-colors group"
        >
          <h3 className="font-serif text-lg text-ink group-hover:text-accent mb-1">
            Run Scanner
          </h3>
          <p className="text-sm text-mid-brown">
            Find stocks meeting your technical criteria
          </p>
        </Link>
        <Link
          to="/alerts"
          className="border-2 border-ink shadow-hard bg-warm-white p-6 hover:bg-cream transition-colors group"
        >
          <h3 className="font-serif text-lg text-ink group-hover:text-accent mb-1">
            Create Alert
          </h3>
          <p className="text-sm text-mid-brown">
            Get notified when conditions are met
          </p>
        </Link>
        <Link
          to="/watchlist"
          className="border-2 border-ink shadow-hard bg-warm-white p-6 hover:bg-cream transition-colors group"
        >
          <h3 className="font-serif text-lg text-ink group-hover:text-accent mb-1">
            Add Ticker
          </h3>
          <p className="text-sm text-mid-brown">
            Track a new stock on your watchlist
          </p>
        </Link>
      </div>
    </div>
  );
}
