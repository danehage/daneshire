import { useState } from "react";
import { Link } from "react-router-dom";
import { useAccounts, usePortfolio, useCommitSnapshot, useCommitTrade, useTrades, useValueHistory } from "../hooks/usePortfolio";
import PortfolioHeroCard from "../components/portfolio/PortfolioHeroCard";
import ValueHistoryChart from "../components/portfolio/ValueHistoryChart";

function AccountSelector({ accounts, selectedId, onSelect }) {
  return (
    <select
      value={selectedId ?? ""}
      onChange={(e) => onSelect(e.target.value || null)}
      className="px-3 py-2 border-2 border-ink bg-warm-white text-sm font-mono"
    >
      <option value="">All accounts</option>
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name}
          {a.account_type ? ` (${a.account_type})` : ""}
        </option>
      ))}
    </select>
  );
}

function HoldingsBadge({ type }) {
  if (type === "option") {
    return (
      <span className="px-1 py-0.5 text-xs font-mono border border-accent text-accent uppercase">
        OPT
      </span>
    );
  }
  return null;
}

function HoldingsTable({ positions }) {
  if (positions.length === 0) {
    return (
      <div className="p-8 text-center text-mid-brown font-mono text-sm">
        No positions in this snapshot.
      </div>
    );
  }

  return (
    <table className="w-full text-sm font-mono">
      <thead>
        <tr className="border-b-2 border-ink">
          <th className="text-left py-2 px-3 font-bold uppercase text-xs tracking-wide">Ticker</th>
          <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Qty</th>
          <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Avg Cost</th>
          <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Mkt Value</th>
          <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Day Chg</th>
          <th className="text-left py-2 px-3 font-bold uppercase text-xs tracking-wide">Type</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((pos, i) => {
          const dayChgNum = pos.day_change != null ? Number(pos.day_change) : null;
          const isPositive = dayChgNum != null && dayChgNum > 0;
          const isNegative = dayChgNum != null && dayChgNum < 0;
          return (
            <tr key={i} className="border-b border-ink/20 hover:bg-cream/50">
              <td className="py-2 px-3">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/ticker/${pos.ticker}`}
                    className="font-bold text-ink hover:text-accent transition-colors"
                  >
                    {pos.ticker}
                  </Link>
                  {pos.instrument_type === "option" && pos.underlying_ticker && (
                    <span className="text-xs text-mid-brown">
                      / {pos.underlying_ticker}
                    </span>
                  )}
                </div>
                {pos.instrument_type === "option" && (
                  <div className="text-xs text-mid-brown">
                    {pos.option_type?.toUpperCase()} ${pos.strike} exp {pos.expiry}
                  </div>
                )}
              </td>
              <td className="py-2 px-3 text-right">{Number(pos.qty).toLocaleString()}</td>
              <td className="py-2 px-3 text-right">${Number(pos.avg_cost).toFixed(2)}</td>
              <td className="py-2 px-3 text-right">
                {pos.market_value != null
                  ? `$${Number(pos.market_value).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}`
                  : "—"}
              </td>
              <td
                className={`py-2 px-3 text-right ${
                  isPositive ? "text-green-700" : isNegative ? "text-red-700" : "text-ink"
                }`}
              >
                {dayChgNum != null
                  ? `${dayChgNum >= 0 ? "+" : ""}$${Math.abs(dayChgNum).toFixed(2)}`
                  : "—"}
              </td>
              <td className="py-2 px-3">
                <HoldingsBadge type={pos.instrument_type} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function CommitSnapshotForm({ onSuccess }) {
  const commitMutation = useCommitSnapshot();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    account_name: "",
    account_type: "",
    captured_at: new Date().toISOString().slice(0, 16),
    cash_balance: "",
    total_value: "",
    positions_json: "[]",
  });
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    let positions;
    try {
      positions = JSON.parse(form.positions_json);
    } catch {
      setError("Positions must be valid JSON.");
      return;
    }
    try {
      await commitMutation.mutateAsync({
        account_name: form.account_name,
        account_type: form.account_type || undefined,
        captured_at: new Date(form.captured_at).toISOString(),
        cash_balance: form.cash_balance || undefined,
        total_value: form.total_value || undefined,
        positions,
      });
      setOpen(false);
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink bg-ink text-warm-white hover:bg-dark-brown transition-all"
      >
        + Commit Snapshot
      </button>
    );
  }

  return (
    <div className="bg-warm-white border-2 border-ink p-4 mb-6">
      <h2 className="font-serif font-bold text-lg mb-4">Commit Portfolio Snapshot</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Account Name *</label>
            <input
              required
              value={form.account_name}
              onChange={(e) => setForm({ ...form, account_name: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="Taxable"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Account Type</label>
            <input
              value={form.account_type}
              onChange={(e) => setForm({ ...form, account_type: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="individual, roth, ira…"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Captured At *</label>
            <input
              required
              type="datetime-local"
              value={form.captured_at}
              onChange={(e) => setForm({ ...form, captured_at: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Cash Balance</label>
            <input
              type="number"
              step="0.01"
              value={form.cash_balance}
              onChange={(e) => setForm({ ...form, cash_balance: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="5000.00"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Total Value</label>
            <input
              type="number"
              step="0.01"
              value={form.total_value}
              onChange={(e) => setForm({ ...form, total_value: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="25000.00"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">
            Positions (JSON array)
          </label>
          <textarea
            rows={6}
            value={form.positions_json}
            onChange={(e) => setForm({ ...form, positions_json: e.target.value })}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-xs bg-cream"
            placeholder='[{"instrument_type":"equity","ticker":"AAPL","qty":"10","avg_cost":"180.00"}]'
          />
        </div>
        {error && <p className="text-red-600 text-sm font-mono">{error}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={commitMutation.isPending}
            className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink bg-ink text-warm-white hover:bg-dark-brown disabled:opacity-50"
          >
            {commitMutation.isPending ? "Saving…" : "Save Snapshot"}
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink hover:bg-cream"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function CommitTradeForm({ accountId, onSuccess }) {
  const commitMutation = useCommitTrade();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    ticker: "",
    instrument_type: "equity",
    side: "buy",
    qty: "",
    price: "",
    executed_at: new Date().toISOString().slice(0, 16),
  });
  const [error, setError] = useState(null);
  const [lastWarnings, setLastWarnings] = useState([]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLastWarnings([]);
    try {
      const result = await commitMutation.mutateAsync({
        account_id: accountId,
        ticker: form.ticker,
        instrument_type: form.instrument_type,
        side: form.side,
        qty: form.qty,
        price: form.price,
        executed_at: new Date(form.executed_at).toISOString(),
      });
      if (result.warnings?.length > 0) {
        setLastWarnings(result.warnings);
      } else {
        setOpen(false);
      }
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink hover:bg-cream transition-all"
      >
        + Log Trade
      </button>
    );
  }

  return (
    <div className="bg-warm-white border-2 border-ink p-4 mb-4">
      <h2 className="font-serif font-bold text-lg mb-4">Log Trade</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Ticker *</label>
            <input
              required
              value={form.ticker}
              onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="AAPL"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Side *</label>
            <select
              value={form.side}
              onChange={(e) => setForm({ ...form, side: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Type *</label>
            <select
              value={form.instrument_type}
              onChange={(e) => setForm({ ...form, instrument_type: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            >
              <option value="equity">Equity</option>
              <option value="option">Option</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Qty *</label>
            <input
              required
              type="number"
              step="0.000001"
              min="0.000001"
              value={form.qty}
              onChange={(e) => setForm({ ...form, qty: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="10"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Price *</label>
            <input
              required
              type="number"
              step="0.0001"
              min="0"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="190.00"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Executed At *</label>
            <input
              required
              type="datetime-local"
              value={form.executed_at}
              onChange={(e) => setForm({ ...form, executed_at: e.target.value })}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            />
          </div>
        </div>
        {lastWarnings.length > 0 && (
          <div className="p-2 border border-amber-400 bg-amber-50 text-amber-800 text-xs font-mono">
            {lastWarnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
          </div>
        )}
        {error && <p className="text-red-600 text-sm font-mono">{error}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={commitMutation.isPending}
            className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink bg-ink text-warm-white hover:bg-dark-brown disabled:opacity-50"
          >
            {commitMutation.isPending ? "Saving…" : "Save Trade"}
          </button>
          <button
            type="button"
            onClick={() => { setOpen(false); setLastWarnings([]); }}
            className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink hover:bg-cream"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function TradeLog({ accountId }) {
  const { data: trades, isLoading } = useTrades(accountId ? { accountId } : undefined);

  if (!accountId) return null;

  return (
    <div className="bg-warm-white border-2 border-ink shadow-hard mt-6">
      <div className="px-4 py-3 border-b-2 border-ink">
        <h2 className="font-serif font-bold text-lg">Trade Log</h2>
      </div>
      {isLoading ? (
        <div className="p-8 text-center text-mid-brown font-mono text-sm">Loading…</div>
      ) : !trades || trades.length === 0 ? (
        <div className="p-8 text-center text-mid-brown font-mono text-sm">No trades logged yet.</div>
      ) : (
        <>
          <table className="w-full text-sm font-mono">
            <thead>
              <tr className="border-b-2 border-ink">
                <th className="text-left py-2 px-3 font-bold uppercase text-xs tracking-wide">Date</th>
                <th className="text-left py-2 px-3 font-bold uppercase text-xs tracking-wide">Ticker</th>
                <th className="text-left py-2 px-3 font-bold uppercase text-xs tracking-wide">Side</th>
                <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Qty</th>
                <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Price</th>
                <th className="text-right py-2 px-3 font-bold uppercase text-xs tracking-wide">Realized P/L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const pl = t.realized_pl != null ? Number(t.realized_pl) : null;
                const isPos = pl != null && pl > 0;
                const isNeg = pl != null && pl < 0;
                return (
                  <tr key={t.id} className="border-b border-ink/20 hover:bg-cream/50">
                    <td className="py-2 px-3 text-mid-brown">
                      {new Date(t.executed_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 px-3">
                      <Link
                        to={`/ticker/${t.ticker}`}
                        className="font-bold text-ink hover:text-accent transition-colors"
                      >
                        {t.ticker}
                      </Link>
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1 py-0.5 text-xs font-mono uppercase border ${
                          t.side === "buy"
                            ? "border-green-600 text-green-700"
                            : "border-red-500 text-red-600"
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right">{Number(t.qty).toLocaleString()}</td>
                    <td className="py-2 px-3 text-right">${Number(t.price).toFixed(2)}</td>
                    <td
                      className={`py-2 px-3 text-right ${
                        isPos ? "text-green-700" : isNeg ? "text-red-700" : "text-mid-brown"
                      }`}
                    >
                      {pl != null
                        ? `${pl >= 0 ? "+" : ""}$${Math.abs(pl).toFixed(2)}`
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="px-4 py-2 text-xs text-mid-brown font-mono border-t border-ink/20">
            Realized P/L uses average cost and may differ from your broker's 1099-B.
          </p>
        </>
      )}
    </div>
  );
}

export default function PortfolioPage() {
  const { data: accounts, isLoading: accountsLoading } = useAccounts();
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const { data: portfolioData, isLoading: portfolioLoading, error } = usePortfolio(selectedAccountId);
  const { data: historyData } = useValueHistory(selectedAccountId);

  const positions = portfolioData?.positions ?? [];
  const historyPoints = historyData?.points ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-serif font-bold text-ink">Portfolio</h1>
        {!accountsLoading && (
          <AccountSelector
            accounts={accounts ?? []}
            selectedId={selectedAccountId}
            onSelect={setSelectedAccountId}
          />
        )}
      </div>

      <CommitSnapshotForm />

      {selectedAccountId && portfolioData && (
        <PortfolioHeroCard portfolio={portfolioData} />
      )}

      {selectedAccountId && historyPoints.length > 0 && (
        <div className="bg-warm-white border-2 border-ink shadow-hard mb-6">
          <div className="px-4 py-3 border-b-2 border-ink">
            <h2 className="font-serif font-bold text-lg">
              Value History
              <span className="ml-2 text-sm font-mono font-normal text-mid-brown">
                (snapshots + live)
              </span>
            </h2>
          </div>
          <div className="p-2">
            <ValueHistoryChart points={historyPoints} />
          </div>
        </div>
      )}

      <div className="bg-warm-white border-2 border-ink shadow-hard">
        <div className="px-4 py-3 border-b-2 border-ink flex items-center justify-between">
          <h2 className="font-serif font-bold text-lg">
            Current Holdings
            <span className="ml-2 text-sm font-mono font-normal text-mid-brown">
              (snapshot + trades)
            </span>
          </h2>
          {selectedAccountId && (
            <CommitTradeForm accountId={selectedAccountId} />
          )}
        </div>
        {portfolioLoading ? (
          <div className="p-8 text-center text-mid-brown font-mono text-sm">Loading…</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600 font-mono text-sm">{error.message}</div>
        ) : (
          <HoldingsTable positions={positions} />
        )}
      </div>

      <TradeLog accountId={selectedAccountId} />
    </div>
  );
}
