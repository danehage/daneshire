import { Link } from 'react-router-dom';
import { useTickerEarnings } from '../hooks/useEarnings';

const REPORT_TIME_LABEL = {
  bmo: 'Before market open',
  amc: 'After market close',
  unknown: 'Time unknown',
};

const TRADE_STATUS_BADGE = {
  open: 'bg-blue-100 text-blue-800 border-ink',
  closed: 'bg-success text-warm-white border-ink',
  expired: 'bg-light-brown text-warm-white border-ink',
  assigned: 'bg-warning text-warm-white border-ink',
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [year, month, day] = dateStr.split('-');
  return `${month}/${day}/${year}`;
}

function formatPct(value, digits = 2) {
  if (value === null || value === undefined) return '—';
  const num = Number(value);
  if (Number.isNaN(num)) return '—';
  return `${(num * 100).toFixed(digits)}%`;
}

function formatRatio(value, digits = 2) {
  if (value === null || value === undefined) return '—';
  const num = Number(value);
  if (Number.isNaN(num)) return '—';
  return `${num.toFixed(digits)}x`;
}

function Section({ title, children, action }) {
  return (
    <div className="border-2 border-ink bg-warm-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium uppercase tracking-wide text-dark-brown">
          {title}
        </h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function NextEventSection({ event }) {
  if (!event) {
    return (
      <Section title="Next Event">
        <p className="text-sm text-light-brown italic">No upcoming earnings on record.</p>
      </Section>
    );
  }
  return (
    <Section title="Next Event">
      <div className="space-y-1">
        <div className="text-2xl font-serif text-ink">{formatDate(event.report_date)}</div>
        <div className="text-sm text-mid-brown">
          {REPORT_TIME_LABEL[event.report_time] || REPORT_TIME_LABEL.unknown}
          {event.fiscal_period ? ` · ${event.fiscal_period}` : ''}
        </div>
      </div>
    </Section>
  );
}

function IVSnapshotSection({ snapshot }) {
  if (!snapshot) {
    return (
      <Section title="IV Snapshot">
        <p className="text-sm text-light-brown italic">No IV snapshot yet.</p>
      </Section>
    );
  }
  return (
    <Section title="IV Snapshot">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-mid-brown mb-1">IV Rank</div>
          <div className="font-mono text-xl text-ink">
            {Number(snapshot.iv_rank).toFixed(0)}
          </div>
        </div>
        <div>
          <div className="text-xs text-mid-brown mb-1">Expected Move</div>
          <div className="font-mono text-xl text-ink">
            {formatPct(snapshot.expected_move_pct)}
          </div>
        </div>
        <div className="col-span-2 text-xs text-light-brown">
          As of {formatDate(snapshot.snapshot_date)} · {snapshot.source}
        </div>
      </div>
    </Section>
  );
}

function RealizedMoveHistorySection({
  history,
  historicalAvg,
  edgeRatio,
  expectedMovePct,
}) {
  if (!history || history.length === 0) {
    return (
      <Section title="Realized Move History">
        <p className="text-sm text-light-brown italic">No past earnings moves recorded.</p>
      </Section>
    );
  }

  // Sign-stripped per ADR-0003 — values are non-negative percentages
  // (e.g. 0.04 = 4%). Scale bar widths against the largest in the set
  // OR the expected move, whichever is larger, so the expected-move
  // line sits inside the chart.
  const maxFromHistory = history.reduce(
    (m, h) => Math.max(m, Number(h.realized_move_pct) || 0),
    0,
  );
  const emPct = expectedMovePct != null ? Number(expectedMovePct) : null;
  const scale = Math.max(maxFromHistory, emPct ?? 0) || 1;

  return (
    <Section title="Realized Move History">
      <div className="space-y-2">
        {/* Sparkline-friendly CSS bar list (newest first) */}
        <div className="space-y-1">
          {history.map((row) => {
            const pct = Number(row.realized_move_pct);
            const width = `${Math.min(100, (pct / scale) * 100)}%`;
            return (
              <div key={row.report_date} className="flex items-center gap-2 text-xs">
                <div className="w-20 text-mid-brown shrink-0">
                  {formatDate(row.report_date)}
                </div>
                <div className="flex-1 h-4 bg-cream border border-light-brown relative">
                  <div className="absolute inset-y-0 left-0 bg-accent" style={{ width }} />
                  {emPct != null && (
                    <div
                      className="absolute inset-y-0 border-l-2 border-warning"
                      style={{ left: `${Math.min(100, (emPct / scale) * 100)}%` }}
                      title={`Expected move: ${formatPct(emPct)}`}
                    />
                  )}
                </div>
                <div className="w-14 text-right font-mono text-ink">
                  {formatPct(pct)}
                </div>
              </div>
            );
          })}
        </div>

        <div className="pt-2 border-t border-light-brown grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-xs text-mid-brown">Historical Avg</div>
            <div className="font-mono text-ink">{formatPct(historicalAvg)}</div>
          </div>
          <div>
            <div className="text-xs text-mid-brown">Edge Ratio</div>
            <div className="font-mono text-ink">{formatRatio(edgeRatio)}</div>
          </div>
        </div>
      </div>
    </Section>
  );
}

function RecentTradesSection({ trades, ticker }) {
  if (!trades || trades.length === 0) {
    return (
      <Section
        title="Recent Trades"
        action={
          <Link
            to={`/earnings?ticker=${encodeURIComponent(ticker)}`}
            className="text-xs uppercase tracking-wide text-accent hover:underline"
          >
            New Trade →
          </Link>
        }
      >
        <p className="text-sm text-light-brown italic">No trades recorded for this ticker.</p>
      </Section>
    );
  }

  return (
    <Section
      title="Recent Trades"
      action={
        <Link
          to={`/earnings?ticker=${encodeURIComponent(ticker)}`}
          className="text-xs uppercase tracking-wide text-accent hover:underline"
        >
          All Trades →
        </Link>
      }
    >
      <div className="space-y-2">
        {trades.map((trade) => (
          <Link
            key={trade.id}
            to={`/earnings?ticker=${encodeURIComponent(ticker)}&trade=${trade.id}`}
            className="flex items-center justify-between gap-2 p-2 border border-light-brown hover:bg-cream"
          >
            <div className="text-sm">
              <div className="text-ink">
                {trade.structure.replace('_', ' ')}
                {trade.is_paper && (
                  <span className="ml-2 text-xs text-light-brown">paper</span>
                )}
              </div>
              <div className="text-xs text-mid-brown">
                {formatDate(trade.entry_date)} → {formatDate(trade.expiry_date)}
              </div>
            </div>
            <div className="text-right">
              <span
                className={`inline-block text-xs px-2 py-0.5 border ${
                  TRADE_STATUS_BADGE[trade.status] || 'bg-cream text-ink border-ink'
                }`}
              >
                {trade.status}
              </span>
              {trade.pnl_net != null && (
                <div className="text-xs font-mono text-ink mt-1">
                  ${Number(trade.pnl_net).toFixed(2)}
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </Section>
  );
}

export default function EarningsCard({ ticker }) {
  const { data, isLoading, error } = useTickerEarnings(ticker);

  if (isLoading) {
    return (
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6 text-mid-brown">
        Loading earnings data...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="border-2 border-error bg-error/10 p-6 text-error">
        Could not load earnings data: {error?.message || 'unknown error'}
      </div>
    );
  }

  return (
    <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-medium uppercase tracking-wide text-dark-brown">
          Earnings
        </h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <NextEventSection event={data.event} />
        <IVSnapshotSection snapshot={data.latest_iv_snapshot} />
        <div className="md:col-span-2">
          <RealizedMoveHistorySection
            history={data.realized_move_history}
            historicalAvg={data.historical_avg_realized_move_pct}
            edgeRatio={data.edge_ratio}
            expectedMovePct={data.latest_iv_snapshot?.expected_move_pct}
          />
        </div>
        <div className="md:col-span-2">
          <RecentTradesSection trades={data.recent_trades} ticker={ticker} />
        </div>
      </div>
    </div>
  );
}
