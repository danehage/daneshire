import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useEarningsCalendar } from '../hooks/useEarnings';
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

export default function EarningsPage() {
  const today = new Date().toISOString().split('T')[0];
  const end = new Date(Date.now() + 28 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(end);
  const [sortField, setSortField] = useState('report_date');
  const [sortDir, setSortDir] = useState('asc');
  // Secondary sort: when the user is sorting by the default field
  // (`report_date`), break ties by IV rank desc (PRD §3 default).
  const SECONDARY_FIELD = 'latest_iv_rank';

  const { data: events = [], isLoading, isError, error } = useEarningsCalendar({
    start: startDate,
    end: endDate,
  });

  function handleSort(field) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  }

  function compare(a, b, field, dir) {
    const rawA = a[field];
    const rawB = b[field];
    // Nulls always sort last regardless of direction.
    const aMissing = rawA === null || rawA === undefined || rawA === '';
    const bMissing = rawB === null || rawB === undefined || rawB === '';
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;

    let valA = rawA;
    let valB = rawB;
    // IV / move are decimal strings off the wire — compare as numbers.
    if (field === 'latest_iv_rank' || field === 'latest_expected_move_pct') {
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
    if (sortField === 'report_date') {
      // Tie-break by IV rank desc.
      return compare(a, b, SECONDARY_FIELD, 'desc');
    }
    return 0;
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-serif font-bold text-ink mb-1">Earnings Calendar</h1>
        <p className="text-sm text-mid-brown">Upcoming earnings announcements</p>
      </div>

      {/* Date range filter */}
      <div className="flex flex-wrap gap-3 mb-6 items-end">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            From
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border-2 border-ink px-2 py-1 text-sm font-mono bg-warm-white"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            To
          </label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border-2 border-ink px-2 py-1 text-sm font-mono bg-warm-white"
          />
        </div>
      </div>

      {isLoading && (
        <p className="text-mid-brown text-sm">Loading earnings calendar…</p>
      )}

      {isError && (
        <div className="border-2 border-red-500 bg-red-50 p-4 text-red-700 text-sm">
          Failed to load earnings: {error?.message}
        </div>
      )}

      {!isLoading && !isError && sorted.length === 0 && (
        <div className="border-2 border-ink p-8 text-center">
          <p className="text-mid-brown font-medium">No upcoming earnings</p>
          <p className="text-sm text-mid-brown mt-1">
            Try adjusting the date range or run a calendar refresh.
          </p>
        </div>
      )}

      {!isLoading && !isError && sorted.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-2 border-ink text-sm">
            <thead>
              <tr className="border-b-2 border-ink bg-warm-white">
                <th className="px-4 py-3 text-left">
                  <SortButton
                    label="Ticker"
                    field="ticker"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-4 py-3 text-left">
                  <SortButton
                    label="Report Date"
                    field="report_date"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-4 py-3 text-left">
                  <SortButton
                    label="Time"
                    field="report_time"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-4 py-3 text-left">
                  <SortButton
                    label="Period"
                    field="fiscal_period"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-4 py-3 text-right">
                  <SortButton
                    label="IV Rank"
                    field="latest_iv_rank"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
                <th className="px-4 py-3 text-right">
                  <SortButton
                    label="Exp Move %"
                    field="latest_expected_move_pct"
                    sortField={sortField}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((event) => (
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
                    {event.latest_iv_rank !== null && event.latest_iv_rank !== undefined
                      ? Number(event.latest_iv_rank).toFixed(1)
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink">
                    {event.latest_expected_move_pct !== null &&
                    event.latest_expected_move_pct !== undefined
                      ? `${(Number(event.latest_expected_move_pct) * 100).toFixed(2)}%`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-mid-brown mt-2">{sorted.length} events</p>
        </div>
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
