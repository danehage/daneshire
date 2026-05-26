import {
  useEarningsTrades,
  useUpdateEarningsTrade,
  useDeleteEarningsTrade,
} from '../hooks/useEarnings';

const STATUS_BADGE = {
  open: 'bg-blue-100 text-blue-800',
  closed: 'bg-green-100 text-green-800',
  expired: 'bg-gray-200 text-gray-700',
  assigned: 'bg-amber-100 text-amber-800',
};

function fmtMoney(value) {
  if (value === null || value === undefined || value === '') return '—';
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return num.toFixed(2);
}

export default function EarningsTradesList() {
  const { data: trades = [], isLoading, isError, error } = useEarningsTrades();
  const update = useUpdateEarningsTrade();
  const del = useDeleteEarningsTrade();

  async function handleMarkClosed(trade) {
    const debit = window.prompt(
      `Exit debit for ${trade.ticker} (per contract, e.g. 0.40)?`,
      '0.00',
    );
    if (debit === null) return;
    const realized = window.prompt(
      'Realized move % (decimal, e.g. 0.032 for 3.2%) — leave blank to skip',
      '',
    );
    const patch = {
      status: 'closed',
      exit_date: new Date().toISOString().slice(0, 10),
      exit_debit: debit,
    };
    if (realized && realized.trim()) {
      patch.realized_move_pct = realized.trim();
    }
    await update.mutateAsync({ id: trade.id, patch });
  }

  async function handleDelete(trade) {
    const msg = trade.is_paper
      ? `Delete paper trade ${trade.ticker}? This is permanent.`
      : `Soft-close real trade ${trade.ticker}? It will be marked closed.`;
    if (!window.confirm(msg)) return;
    await del.mutateAsync(trade.id);
  }

  if (isLoading) {
    return <p className="text-sm text-mid-brown">Loading trades…</p>;
  }
  if (isError) {
    return (
      <div className="border-2 border-red-500 bg-red-50 p-3 text-red-700 text-sm">
        Failed to load trades: {error?.message}
      </div>
    );
  }
  if (trades.length === 0) {
    return (
      <div className="border-2 border-ink p-6 text-center">
        <p className="text-mid-brown text-sm">No earnings trades logged yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-2 border-ink text-sm">
        <thead>
          <tr className="border-b-2 border-ink bg-warm-white">
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-mid-brown">Ticker</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-mid-brown">Structure</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-mid-brown">Status</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-mid-brown">Credit</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-mid-brown">Debit</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-mid-brown">Ct</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-mid-brown">PnL net</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-mid-brown">Entry</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-mid-brown">Actions</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr
              key={trade.id}
              className="border-b border-gray-200 hover:bg-warm-white"
            >
              <td className="px-3 py-2 font-mono font-bold">
                {trade.ticker}
                {trade.is_paper && (
                  <span className="ml-1 text-[10px] text-mid-brown">(paper)</span>
                )}
              </td>
              <td className="px-3 py-2 text-mid-brown">{trade.structure}</td>
              <td className="px-3 py-2">
                <span
                  className={`inline-block px-2 py-0.5 text-xs font-semibold rounded ${
                    STATUS_BADGE[trade.status] || ''
                  }`}
                >
                  {trade.status}
                </span>
              </td>
              <td className="px-3 py-2 text-right font-mono">{fmtMoney(trade.entry_credit)}</td>
              <td className="px-3 py-2 text-right font-mono">{fmtMoney(trade.exit_debit)}</td>
              <td className="px-3 py-2 text-right font-mono">{trade.contracts}</td>
              <td className="px-3 py-2 text-right font-mono">{fmtMoney(trade.pnl_net)}</td>
              <td className="px-3 py-2 text-mid-brown">{trade.entry_date}</td>
              <td className="px-3 py-2 text-right space-x-2">
                {trade.status === 'open' && (
                  <button
                    onClick={() => handleMarkClosed(trade)}
                    disabled={update.isPending}
                    className="text-xs border border-ink px-2 py-0.5 hover:bg-ink hover:text-warm-white"
                  >
                    Mark closed
                  </button>
                )}
                <button
                  onClick={() => handleDelete(trade)}
                  disabled={del.isPending}
                  className="text-xs border border-red-600 text-red-600 px-2 py-0.5 hover:bg-red-600 hover:text-warm-white"
                >
                  {trade.is_paper ? 'Delete' : 'Close'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-mid-brown mt-2">{trades.length} trades</p>
    </div>
  );
}
