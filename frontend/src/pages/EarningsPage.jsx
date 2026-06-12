import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useEarningsScreen } from '../hooks/useEarnings';
import EarningsTradeForm from '../components/EarningsTradeForm';
import EarningsTradesList from '../components/EarningsTradesList';

const REPORT_TIME_LABEL = {
  bmo: 'BMO',
  amc: 'AMC',
  unknown: '—',
};

const REPORT_TIME_CLASS = {
  bmo: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  amc: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  unknown: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [year, month, day] = dateStr.split('-');
  return `${month}/${day}/${year}`;
}

// Local-time YYYY-MM-DD (toISOString would shift across the UTC boundary).
function localISO(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// Next `count` weekdays starting today (today included if it's a weekday).
// Market holidays aren't excluded — a holiday just shows an empty day.
function nextTradingDays(count) {
  const days = [];
  const d = new Date();
  while (days.length < count) {
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) days.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

function shortDate(d) {
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function SortButton({ label, field, sortField, sortDir, onSort }) {
  const active = sortField === field;
  const arrow = active ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';
  return (
    <button
      onClick={() => onSort(field)}
      className="text-left text-xs font-semibold uppercase tracking-wide text-mid-brown hover:text-ink"
    >
      {label}{arrow}
    </button>
  );
}

function FilterInput({ label, value, onChange, placeholder, type = 'number', min }) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        className="border-2 border-ink px-2 py-1 text-sm font-mono bg-warm-white w-28"
      />
    </div>
  );
}

function EventsTable({ events, sortField, sortDir, onSort }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-2 border-ink text-sm">
        <thead>
          <tr className="border-b-2 border-ink bg-warm-white">
            <th className="px-4 py-3 text-left">
              <SortButton label="Ticker" field="ticker" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-left">
              <SortButton label="Report Date" field="report_date" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-left">
              <SortButton label="Time" field="report_time" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-left">
              <SortButton label="Period" field="fiscal_period" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-right">
              <SortButton label="IV Rank" field="latest_iv_rank" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-right">
              <SortButton label="Exp Move %" field="latest_expected_move_pct" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-right">
              <SortButton label="Avg Realized %" field="historical_avg_realized_move_pct" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
            <th className="px-4 py-3 text-right">
              <SortButton label="Edge Ratio" field="edge_ratio" sortField={sortField} sortDir={sortDir} onSort={onSort} />
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.id}
              className="border-b border-gray-200 dark:border-gray-700 hover:bg-warm-white transition-colors"
            >
              <td className="px-4 py-3 font-mono font-bold">
                <Link
                  to={`/ticker/${event.ticker}`}
                  className="text-accent hover:underline"
                >
                  {event.ticker}
                </Link>
              </td>
              <td className="px-4 py-3 text-ink">{formatDate(event.report_date)}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-block px-2 py-0.5 text-xs font-semibold rounded ${
                    REPORT_TIME_CLASS[event.report_time] || REPORT_TIME_CLASS.unknown
                  }`}
                >
                  {REPORT_TIME_LABEL[event.report_time] ?? event.report_time}
                </span>
              </td>
              <td className="px-4 py-3 text-mid-brown">
                {event.fiscal_period || '—'}
              </td>
              <td className="px-4 py-3 text-right font-mono text-ink">
                {event.latest_iv_rank != null
                  ? Number(event.latest_iv_rank).toFixed(1)
                  : '—'}
              </td>
              <td className="px-4 py-3 text-right font-mono text-ink">
                {event.latest_expected_move_pct != null
                  ? `${(Number(event.latest_expected_move_pct) * 100).toFixed(2)}%`
                  : '—'}
              </td>
              <td className="px-4 py-3 text-right font-mono text-mid-brown">
                {event.historical_avg_realized_move_pct != null
                  ? `${(Number(event.historical_avg_realized_move_pct) * 100).toFixed(2)}%`
                  : '—'}
              </td>
              <td className="px-4 py-3 text-right font-mono font-semibold text-ink">
                {event.edge_ratio != null
                  ? Number(event.edge_ratio).toFixed(2)
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-mid-brown mt-2">{events.length} events</p>
    </div>
  );
}

const DEBOUNCE_MS = 300;

function useDebounced(value, delay = DEBOUNCE_MS) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function EarningsPage() {
  // Fixed window: the next 10 trading days, split 5 (prominent) + 5 (on deck).
  const tradingDays = nextTradingDays(10);
  const startDate = localISO(tradingDays[0]);
  const week1End = localISO(tradingDays[4]);
  const endDate = localISO(tradingDays[9]);

  const [searchParams, setSearchParams] = useSearchParams();

  const [minIvRankInput, setMinIvRankInput] = useState(
    searchParams.get('min_iv_rank') || ''
  );
  const [minEdgeRatioInput, setMinEdgeRatioInput] = useState(
    searchParams.get('min_edge_ratio') || ''
  );
  const [minVolumeInput, setMinVolumeInput] = useState(
    searchParams.get('min_volume') || ''
  );

  // Debounced filter values drive the query.
  const minIvRank = useDebounced(minIvRankInput);
  const minEdgeRatio = useDebounced(minEdgeRatioInput);
  const minVolume = useDebounced(minVolumeInput);

  // Sync state → URL query string.
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const p = {};
    if (minIvRank) p.min_iv_rank = minIvRank;
    if (minEdgeRatio) p.min_edge_ratio = minEdgeRatio;
    if (minVolume) p.min_volume = minVolume;
    setSearchParams(p, { replace: true });
  }, [minIvRank, minEdgeRatio, minVolume, setSearchParams]);

  const [sortField, setSortField] = useState('edge_ratio');
  const [sortDir, setSortDir] = useState('desc');

  const { data: events = [], isLoading, isError, error } = useEarningsScreen({
    start: startDate,
    end: endDate,
    minIvRank: minIvRank || undefined,
    minEdgeRatio: minEdgeRatio || undefined,
    minVolume: minVolume || undefined,
  });

  const handleSort = useCallback((field) => {
    setSortDir((d) => (sortField === field ? (d === 'asc' ? 'desc' : 'asc') : 'asc'));
    setSortField(field);
  }, [sortField]);

  function compare(a, b, field, dir) {
    const rawA = a[field];
    const rawB = b[field];
    const aMissing = rawA === null || rawA === undefined || rawA === '';
    const bMissing = rawB === null || rawB === undefined || rawB === '';
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;

    let valA = rawA;
    let valB = rawB;
    if (
      field === 'latest_iv_rank' ||
      field === 'latest_expected_move_pct' ||
      field === 'edge_ratio' ||
      field === 'historical_avg_realized_move_pct'
    ) {
      valA = Number(valA);
      valB = Number(valB);
    } else if (typeof valA === 'string') {
      valA = valA.toLowerCase();
      valB = valB.toLowerCase();
    }
    if (valA < valB) return dir === 'asc' ? -1 : 1;
    if (valA > valB) return dir === 'asc' ? 1 : -1;
    return 0;
  }

  const sorted = [...events].sort((a, b) => {
    const primary = compare(a, b, sortField, sortDir);
    if (primary !== 0) return primary;
    // Tie-break: IV rank desc, then report_date asc.
    const byIv = compare(a, b, 'latest_iv_rank', 'desc');
    if (byIv !== 0) return byIv;
    return compare(a, b, 'report_date', 'asc');
  });

  // ISO dates compare correctly as strings.
  const thisWeek = sorted.filter((e) => e.report_date <= week1End);
  const onDeck = sorted.filter((e) => e.report_date > week1End);

  const hasFilters = Boolean(minIvRank || minEdgeRatio || minVolume);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-serif font-bold text-ink mb-1">Earnings Screener</h1>
        <p className="text-sm text-mid-brown">
          Next 10 trading days of earnings with IV rank, expected move, and edge ratio
        </p>
      </div>

      {/* Screener filters */}
      <div className="flex flex-wrap gap-3 mb-6 items-end">
        <FilterInput
          label="Min IV Rank"
          value={minIvRankInput}
          onChange={setMinIvRankInput}
          placeholder="e.g. 50"
          min="0"
        />
        <FilterInput
          label="Min Edge Ratio"
          value={minEdgeRatioInput}
          onChange={setMinEdgeRatioInput}
          placeholder="e.g. 1.2"
          min="0"
        />
        <FilterInput
          label="Min Volume"
          value={minVolumeInput}
          onChange={setMinVolumeInput}
          placeholder="e.g. 500000"
          min="0"
        />

        {hasFilters && (
          <button
            onClick={() => {
              setMinIvRankInput('');
              setMinEdgeRatioInput('');
              setMinVolumeInput('');
            }}
            className="text-xs text-mid-brown underline hover:text-ink self-end mb-1"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && (
        <p className="text-mid-brown text-sm">Loading screener…</p>
      )}

      {isError && (
        <div className="border-2 border-red-500 bg-red-50 p-4 text-red-700 text-sm">
          Failed to load: {error?.message}
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <h2 className="text-lg font-serif font-bold text-ink mb-2">
            This week{' '}
            <span className="text-sm font-sans font-normal text-mid-brown">
              {shortDate(tradingDays[0])} – {shortDate(tradingDays[4])}
            </span>
          </h2>
          {thisWeek.length > 0 ? (
            <EventsTable
              events={thisWeek}
              sortField={sortField}
              sortDir={sortDir}
              onSort={handleSort}
            />
          ) : (
            <div className="border-2 border-ink p-6 text-center mb-2">
              <p className="text-mid-brown font-medium">
                No events in the next 5 trading days
              </p>
              <p className="text-sm text-mid-brown mt-1">
                {hasFilters
                  ? 'Try relaxing the filters.'
                  : 'Try running a calendar refresh.'}
              </p>
            </div>
          )}

          <div className="mt-8 opacity-80">
            <h2 className="text-base font-serif font-bold text-mid-brown mb-2">
              On deck{' '}
              <span className="text-sm font-sans font-normal">
                {shortDate(tradingDays[5])} – {shortDate(tradingDays[9])}
              </span>
            </h2>
            {onDeck.length > 0 ? (
              <EventsTable
                events={onDeck}
                sortField={sortField}
                sortDir={sortDir}
                onSort={handleSort}
              />
            ) : (
              <p className="text-sm text-mid-brown border-2 border-ink p-4">
                No events in the following 5 trading days.
              </p>
            )}
          </div>
        </>
      )}

      <div className="mt-10">
        <h2 className="text-xl font-serif font-bold text-ink mb-1">
          Earnings trades
        </h2>
        <p className="text-sm text-mid-brown mb-4">
          Log iron condors / butterflies sold against the calendar.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EarningsTradeForm earningsEvents={events} />
          <EarningsTradesList />
        </div>
      </div>
    </div>
  );
}
