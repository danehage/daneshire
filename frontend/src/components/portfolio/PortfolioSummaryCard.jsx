import { Link } from "react-router-dom";

function freshnessLabel(lastSnapshotAt) {
  if (!lastSnapshotAt) return null;
  const snapshotDate = new Date(lastSnapshotAt);
  const now = new Date();
  const diffDays = Math.floor((now - snapshotDate) / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return "snapshot from today";
  if (diffDays === 1) return "snapshot from 1 day ago";
  return `snapshot from ${diffDays} days ago`;
}

function fmt(value) {
  if (value == null) return "—";
  const n = Number(value);
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PortfolioSummaryCard({ portfolio }) {
  if (!portfolio || portfolio.account_id == null) {
    return (
      <div className="border-2 border-ink shadow-hard-sm sm:shadow-hard bg-warm-white p-4 sm:p-6">
        <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
          Portfolio
        </h3>
        <Link
          to="/portfolio"
          className="inline-block text-sm text-accent hover:text-accent-hover font-medium"
        >
          Upload your first snapshot →
        </Link>
      </div>
    );
  }

  const { total_value, day_change, last_snapshot_at } = portfolio;
  const dayChangeNum = day_change != null ? Number(day_change) : null;
  const isPositive = dayChangeNum != null && dayChangeNum > 0;
  const isNegative = dayChangeNum != null && dayChangeNum < 0;
  const freshness = freshnessLabel(last_snapshot_at);

  const dayChangePct =
    dayChangeNum != null && total_value && Number(total_value) !== 0
      ? ((dayChangeNum / (Number(total_value) - dayChangeNum)) * 100).toFixed(2)
      : null;

  return (
    <div className="border-2 border-ink shadow-hard-sm sm:shadow-hard bg-warm-white p-4 sm:p-6">
      <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown mb-2">
        Portfolio
      </h3>
      <p className="text-3xl sm:text-4xl font-serif font-bold text-ink mb-1">
        ${fmt(total_value)}
      </p>
      {dayChangeNum != null && (
        <p
          className={`text-sm font-mono mb-1 ${
            isPositive ? "text-green-700" : isNegative ? "text-red-700" : "text-mid-brown"
          }`}
        >
          {dayChangeNum >= 0 ? "+" : ""}${fmt(day_change)}
          {dayChangePct != null && ` (${dayChangeNum >= 0 ? "+" : ""}${dayChangePct}%)`}
        </p>
      )}
      {freshness && (
        // TODO: wire to UploadReviewModal when #11 ships
        <button
          type="button"
          onClick={() => {}}
          className="text-xs text-light-brown hover:text-accent underline underline-offset-2 transition-colors"
        >
          {freshness}
        </button>
      )}
      <Link
        to="/portfolio"
        className="inline-block mt-3 text-sm text-accent hover:text-accent-hover font-medium"
      >
        View portfolio →
      </Link>
    </div>
  );
}
