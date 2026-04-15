import { useState } from "react";
import { useUniverses, useScan } from "../hooks/useScanner";
import { useCreateWatchlistItem } from "../hooks/useWatchlist";

function UniverseSelector({ value, onChange, universes }) {
  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown">
        Universe
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-4 py-3 border-2 border-ink bg-warm-white text-ink font-serif"
      >
        {universes?.map((u) => (
          <option key={u.name} value={u.name}>
            {u.name.toUpperCase()} ({u.size} stocks) — {u.description}
          </option>
        ))}
      </select>
    </div>
  );
}

function ProgressBar({ current, total, found, errors }) {
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm text-mid-brown">
        <span>
          Analyzing {current} of {total}
          {errors > 0 && (
            <span className="text-warning ml-2">({errors} errors)</span>
          )}
        </span>
        <span>{found} opportunities found</span>
      </div>
      <div className="h-4 border-2 border-ink bg-cream">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function SignalBadge({ signal }) {
  // Color code based on signal content
  let colorClass = "bg-warm-white text-dark-brown border-light-brown";

  if (signal.includes("HV") || signal.includes("volatility")) {
    colorClass = "bg-warning text-warm-white border-ink";
  } else if (signal.includes("Oversold") || signal.includes("RSI low")) {
    colorClass = "bg-success text-warm-white border-ink";
  } else if (signal.includes("Overbought") || signal.includes("RSI elevated")) {
    colorClass = "bg-error text-warm-white border-ink";
  } else if (signal.includes("support") || signal.includes("Uptrend")) {
    colorClass = "bg-accent text-warm-white border-ink";
  } else if (signal.includes("value") || signal.includes("Deep")) {
    colorClass = "bg-success text-warm-white border-ink";
  } else if (signal.includes("cap") || signal.includes("liquid")) {
    colorClass = "bg-light-brown text-warm-white border-ink";
  }

  return (
    <span
      className={`inline-block text-xs px-2 py-0.5 border ${colorClass} mr-1 mb-1`}
    >
      {signal}
    </span>
  );
}

function ResultRow({ result, onAddToWatchlist, isAdding }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className={`border-b-2 border-ink hover:bg-warm-white transition-colors cursor-pointer ${
          expanded ? "bg-warm-white" : ""
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-3 px-4">
          <div className="flex items-center gap-2">
            <span
              className={`text-xs transition-transform ${
                expanded ? "rotate-90" : ""
              }`}
            >
              ▶
            </span>
            <span className="font-serif text-lg text-ink">{result.ticker}</span>
          </div>
        </td>
        <td className="py-3 px-4 font-mono">${result.price.toFixed(2)}</td>
        <td className="py-3 px-4">
          <span
            className={`inline-block px-3 py-1 text-sm font-bold border-2 border-ink ${
              result.score >= 50
                ? "bg-success text-warm-white"
                : result.score >= 30
                ? "bg-warning text-warm-white"
                : "bg-cream text-ink"
            }`}
          >
            {result.score}
          </span>
        </td>
        <td className="py-3 px-4 text-sm text-mid-brown">{result.trend}</td>
        <td className="py-3 px-4 text-sm">
          {result.hv_rank ? `${result.hv_rank.toFixed(0)}%` : "—"}
        </td>
        <td className="py-3 px-4 text-sm">{result.rsi.toFixed(0)}</td>
        <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onAddToWatchlist(result)}
            disabled={isAdding}
            className="px-3 py-1 text-xs font-medium uppercase tracking-wide border-2 border-ink bg-accent text-warm-white hover:bg-accent-hover shadow-hard-sm disabled:opacity-50"
          >
            {isAdding ? "..." : "+ Add"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-cream border-b-2 border-ink">
          <td colSpan={7} className="px-6 py-4">
            <div className="grid grid-cols-4 gap-6 text-sm">
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Price Levels
                </h4>
                <p>
                  <span className="text-mid-brown">Support:</span> $
                  {result.support.toFixed(2)}
                </p>
                <p>
                  <span className="text-mid-brown">Resistance:</span> $
                  {result.resistance.toFixed(2)}
                </p>
                <p>
                  <span className="text-mid-brown">52w Range:</span>{" "}
                  {result.range_position.toFixed(0)}%
                </p>
              </div>
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Moving Averages
                </h4>
                <p>
                  <span className="text-mid-brown">Dist 50-MA:</span>{" "}
                  {result.dist_50?.toFixed(1) ?? "—"}%
                </p>
                <p>
                  <span className="text-mid-brown">Dist 200-MA:</span>{" "}
                  {result.dist_200?.toFixed(1) ?? "—"}%
                </p>
                <p>
                  <span className="text-mid-brown">MA Slope:</span>{" "}
                  {result.ma_slope?.toFixed(2) ?? "—"}%
                </p>
              </div>
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Volume
                </h4>
                <p>
                  <span className="text-mid-brown">Volume:</span>{" "}
                  {(result.volume / 1000000).toFixed(2)}M
                </p>
                <p>
                  <span className="text-mid-brown">Avg Volume:</span>{" "}
                  {(result.avg_volume / 1000000).toFixed(2)}M
                </p>
                <p>
                  <span className="text-mid-brown">Pace:</span>{" "}
                  {result.volume_pace.toFixed(2)}x
                  {result.volume_pace_reliable && " ✓"}
                </p>
              </div>
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                  Volatility
                </h4>
                <p>
                  <span className="text-mid-brown">HV Rank:</span>{" "}
                  {result.hv_rank?.toFixed(0) ?? "—"}%
                </p>
                <p>
                  <span className="text-mid-brown">Current HV:</span>{" "}
                  {result.current_hv?.toFixed(1) ?? "—"}%
                </p>
                <p>
                  <span className="text-mid-brown">10d Momentum:</span>{" "}
                  {result.momentum_10d.toFixed(1)}%
                </p>
              </div>
            </div>
            <div className="mt-4">
              <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
                Signals
              </h4>
              <div className="flex flex-wrap">
                {result.signals.map((signal, i) => (
                  <SignalBadge key={i} signal={signal} />
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ResultsTable({ results, onAddToWatchlist, addingTicker }) {
  if (!results || results.length === 0) {
    return (
      <div className="text-center py-12 text-mid-brown">
        No results to display
      </div>
    );
  }

  return (
    <div className="border-2 border-ink shadow-hard bg-warm-white overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b-2 border-ink bg-cream">
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Ticker
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Price
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Score
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Trend
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              HV Rank
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              RSI
            </th>
            <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-dark-brown">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <ResultRow
              key={result.ticker}
              result={result}
              onAddToWatchlist={onAddToWatchlist}
              isAdding={addingTicker === result.ticker}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ScannerPage() {
  const [selectedUniverse, setSelectedUniverse] = useState("quick");
  const [useCache, setUseCache] = useState(true);
  const [addingTicker, setAddingTicker] = useState(null);

  const { data: universes, isLoading: universesLoading } = useUniverses();
  const {
    startScan,
    isStarting,
    progress,
    isScanning,
    results,
    resultsLoading,
    error,
    reset,
  } = useScan();

  const addToWatchlist = useCreateWatchlistItem();

  const handleStartScan = () => {
    reset();
    startScan({ universe: selectedUniverse, use_cache: useCache });
  };

  const handleAddToWatchlist = async (result) => {
    setAddingTicker(result.ticker);
    try {
      await addToWatchlist.mutateAsync({
        ticker: result.ticker,
        status: "watching",
        tags: result.signals.slice(0, 3), // First 3 signals as tags
      });
    } finally {
      setAddingTicker(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-serif text-4xl text-ink mb-2">Scanner</h1>
        <p className="text-mid-brown">
          Find opportunities with technical analysis
        </p>
      </div>

      {/* Controls */}
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <UniverseSelector
            value={selectedUniverse}
            onChange={setSelectedUniverse}
            universes={universes}
          />

          <div className="space-y-2">
            <label className="block text-xs font-medium uppercase tracking-wide text-dark-brown">
              Options
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useCache}
                onChange={(e) => setUseCache(e.target.checked)}
                className="w-4 h-4 border-2 border-ink"
              />
              <span className="text-sm text-ink">
                Use cached quotes (faster)
              </span>
            </label>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleStartScan}
              disabled={isStarting || isScanning || universesLoading}
              className="w-full px-6 py-3 bg-accent text-warm-white font-medium uppercase tracking-wide border-2 border-ink shadow-hard hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isStarting
                ? "Starting..."
                : isScanning
                ? "Scanning..."
                : "Run Scan"}
            </button>
          </div>
        </div>
      </div>

      {/* Progress */}
      {isScanning && progress && (
        <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
          <ProgressBar
            current={progress.current}
            total={progress.total}
            found={progress.found}
            errors={progress.errors}
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border-2 border-error bg-error/10 p-4 text-error">
          {error}
        </div>
      )}

      {/* Results */}
      {results && !isScanning && (
        <div className="space-y-4">
          {/* Warning banner if there were errors */}
          {results.warning && (
            <div className="border-2 border-warning bg-warning/10 p-4 text-warning">
              <strong>Warning:</strong> {results.warning}
            </div>
          )}

          <div className="flex items-center justify-between">
            <h2 className="font-serif text-2xl text-ink">
              Results ({results.results.length} opportunities)
            </h2>
            <span className="text-sm text-mid-brown">
              Scanned {results.total_analyzed} stocks
              {results.errors > 0 && (
                <span className="text-warning ml-1">
                  ({results.errors} failed)
                </span>
              )}
            </span>
          </div>
          <ResultsTable
            results={results.results}
            onAddToWatchlist={handleAddToWatchlist}
            addingTicker={addingTicker}
          />
        </div>
      )}

      {/* Loading results */}
      {resultsLoading && (
        <div className="text-center py-12 text-mid-brown">
          Loading results...
        </div>
      )}
    </div>
  );
}
