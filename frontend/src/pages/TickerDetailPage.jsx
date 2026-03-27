import { useParams, Link } from "react-router-dom";
import { useTickerAnalysis, useTickerWatchlistItem } from "../hooks/useTicker";
import { useCreateWatchlistItem } from "../hooks/useWatchlist";
import PriceTargets from "../components/PriceTargets";
import JournalEntries from "../components/JournalEntries";

function SignalBadge({ signal }) {
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

function TrendBadge({ trend }) {
  const colorClass =
    trend === "Uptrend"
      ? "bg-success text-warm-white"
      : trend === "Downtrend"
      ? "bg-error text-warm-white"
      : "bg-warm-white text-dark-brown";

  return (
    <span className={`px-3 py-1 text-sm font-medium border-2 border-ink ${colorClass}`}>
      {trend}
    </span>
  );
}

function ScoreBadge({ score }) {
  const colorClass =
    score >= 50
      ? "bg-success text-warm-white"
      : score >= 30
      ? "bg-warning text-warm-white"
      : "bg-cream text-ink";

  return (
    <span className={`px-4 py-2 text-2xl font-bold border-2 border-ink ${colorClass}`}>
      {score}
    </span>
  );
}

function StatCard({ label, value, subValue }) {
  return (
    <div className="bg-warm-white border-2 border-ink p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-mid-brown mb-1">
        {label}
      </div>
      <div className="text-xl font-serif text-ink">{value}</div>
      {subValue && <div className="text-xs text-light-brown mt-1">{subValue}</div>}
    </div>
  );
}

function formatMarketCap(value) {
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toLocaleString()}`;
}

function formatVolume(value) {
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toLocaleString();
}

export default function TickerDetailPage() {
  const { symbol } = useParams();
  const {
    data: analysis,
    isLoading: analysisLoading,
    error: analysisError,
  } = useTickerAnalysis(symbol);
  const { data: watchlistItem, isLoading: watchlistLoading } =
    useTickerWatchlistItem(symbol);
  const addToWatchlist = useCreateWatchlistItem();

  const handleAddToWatchlist = () => {
    addToWatchlist.mutate({
      ticker: symbol.toUpperCase(),
      status: "watching",
      tags: analysis?.signals?.slice(0, 3) || [],
    });
  };

  if (analysisLoading) {
    return (
      <div className="py-12 text-center text-mid-brown">
        Analyzing {symbol?.toUpperCase()}...
      </div>
    );
  }

  if (analysisError) {
    return (
      <div className="py-12">
        <div className="border-2 border-error bg-error/10 p-6 text-error text-center">
          <p className="text-lg font-medium mb-2">Could not analyze {symbol?.toUpperCase()}</p>
          <p className="text-sm">{analysisError.message}</p>
          <Link
            to="/scanner"
            className="inline-block mt-4 px-4 py-2 bg-accent text-warm-white text-sm font-medium uppercase tracking-wide border-2 border-ink"
          >
            Back to Scanner
          </Link>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="py-12 text-center text-mid-brown">
        Loading {symbol?.toUpperCase()}...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-4 mb-2">
            <h1 className="font-serif text-4xl text-ink">{analysis.ticker}</h1>
            <TrendBadge trend={analysis.trend} />
          </div>
          <div className="flex items-baseline gap-4">
            <span className="text-3xl font-mono text-ink">
              ${analysis.price.toFixed(2)}
            </span>
            <span className="text-lg text-mid-brown">
              {formatMarketCap(analysis.market_cap)} market cap
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs font-medium uppercase tracking-wide text-mid-brown mb-1">
              Score
            </div>
            <ScoreBadge score={analysis.score} />
          </div>
          {!watchlistLoading && !watchlistItem && (
            <button
              onClick={handleAddToWatchlist}
              disabled={addToWatchlist.isPending}
              className="px-6 py-3 bg-accent text-warm-white font-medium uppercase tracking-wide border-2 border-ink shadow-hard hover:bg-accent-hover disabled:opacity-50"
            >
              {addToWatchlist.isPending ? "Adding..." : "+ Add to Watchlist"}
            </button>
          )}
          {watchlistItem && (
            <Link
              to="/watchlist"
              className="px-4 py-2 bg-success text-warm-white text-sm font-medium uppercase tracking-wide border-2 border-ink"
            >
              On Watchlist
            </Link>
          )}
        </div>
      </div>

      {/* Signals */}
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
        <h2 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-3">
          Signals
        </h2>
        <div className="flex flex-wrap">
          {analysis.signals.length > 0 ? (
            analysis.signals.map((signal, i) => (
              <SignalBadge key={i} signal={signal} />
            ))
          ) : (
            <span className="text-light-brown italic">No signals detected</span>
          )}
        </div>
      </div>

      {/* Technical Analysis Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="RSI (14)"
          value={analysis.rsi.toFixed(1)}
          subValue={
            analysis.rsi < 30
              ? "Oversold"
              : analysis.rsi > 70
              ? "Overbought"
              : "Neutral"
          }
        />
        <StatCard
          label="HV Rank"
          value={analysis.hv_rank ? `${analysis.hv_rank.toFixed(0)}%` : "N/A"}
          subValue={
            analysis.current_hv
              ? `Current HV: ${analysis.current_hv.toFixed(1)}%`
              : null
          }
        />
        <StatCard
          label="10d Momentum"
          value={`${analysis.momentum_10d >= 0 ? "+" : ""}${analysis.momentum_10d.toFixed(1)}%`}
        />
        <StatCard
          label="52w Range"
          value={`${analysis.range_position.toFixed(0)}%`}
          subValue={`$${analysis.low_52w.toFixed(2)} - $${analysis.high_52w.toFixed(2)}`}
        />
      </div>

      {/* Price Levels & Moving Averages */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
          <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-4">
            Price Levels
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-light-brown">
              <span className="text-mid-brown">Support</span>
              <div className="text-right">
                <span className="font-mono text-ink">
                  ${analysis.support.toFixed(2)}
                </span>
                <span className="text-xs text-light-brown ml-2">
                  ({analysis.support_type})
                </span>
              </div>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-light-brown">
              <span className="text-mid-brown">Resistance</span>
              <div className="text-right">
                <span className="font-mono text-ink">
                  ${analysis.resistance.toFixed(2)}
                </span>
                <span className="text-xs text-light-brown ml-2">
                  ({analysis.resistance_type})
                </span>
              </div>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-light-brown">
              <span className="text-mid-brown">52w High</span>
              <span className="font-mono text-ink">
                ${analysis.high_52w.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-mid-brown">52w Low</span>
              <span className="font-mono text-ink">
                ${analysis.low_52w.toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
          <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-4">
            Moving Averages
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-light-brown">
              <span className="text-mid-brown">Distance to 50-MA</span>
              <span className="font-mono text-ink">
                {analysis.dist_50 !== null
                  ? `${analysis.dist_50 >= 0 ? "+" : ""}${analysis.dist_50.toFixed(1)}%`
                  : "N/A"}
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-light-brown">
              <span className="text-mid-brown">Distance to 200-MA</span>
              <span className="font-mono text-ink">
                {analysis.dist_200 !== null
                  ? `${analysis.dist_200 >= 0 ? "+" : ""}${analysis.dist_200.toFixed(1)}%`
                  : "N/A"}
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-mid-brown">MA Slope (20d)</span>
              <span className="font-mono text-ink">
                {analysis.ma_slope !== null
                  ? `${analysis.ma_slope >= 0 ? "+" : ""}${analysis.ma_slope.toFixed(2)}%`
                  : "N/A"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Volume */}
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
        <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-4">
          Volume Analysis
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="text-mid-brown text-sm mb-1">Today's Volume</div>
            <div className="font-mono text-lg text-ink">
              {formatVolume(analysis.volume)}
            </div>
          </div>
          <div>
            <div className="text-mid-brown text-sm mb-1">Average Volume</div>
            <div className="font-mono text-lg text-ink">
              {formatVolume(analysis.avg_volume)}
            </div>
          </div>
          <div>
            <div className="text-mid-brown text-sm mb-1">Volume Ratio</div>
            <div className="font-mono text-lg text-ink">
              {analysis.volume_ratio.toFixed(2)}x
            </div>
          </div>
          <div>
            <div className="text-mid-brown text-sm mb-1">Volume Pace</div>
            <div className="font-mono text-lg text-ink">
              {analysis.volume_pace.toFixed(2)}x
              {analysis.volume_pace_reliable && (
                <span className="text-success text-sm ml-1">*</span>
              )}
            </div>
            {analysis.volume_pace_reliable && (
              <div className="text-xs text-light-brown">Time-adjusted</div>
            )}
          </div>
        </div>
      </div>

      {/* Watchlist Data (if on watchlist) */}
      {watchlistItem && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
            <PriceTargets
              watchlistId={watchlistItem.id}
              ticker={watchlistItem.ticker}
            />
          </div>
          <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
            <JournalEntries watchlistId={watchlistItem.id} />
          </div>
        </div>
      )}
    </div>
  );
}
