import { useState } from "react";
import { useAccounts, useCommitTrade } from "../../hooks/usePortfolio";

export default function TradeReviewPane({ parseData, onCommit, onCancel }) {
  const { data: accounts } = useAccounts();
  const commitMutation = useCommitTrade();

  const parsed = parseData.parsed_trade;

  // datetime-local inputs hold LOCAL wall-clock time; toISOString() is UTC.
  // Same round-trip discipline as SnapshotReviewPane.
  const toLocalInputValue = (date) => {
    const d = date ? new Date(date) : new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  };

  const [form, setForm] = useState({
    account_id: parseData.account_id ?? "",
    ticker: parsed.ticker ?? "",
    instrument_type: parsed.instrument_type ?? "equity",
    side: parsed.side ?? "buy",
    qty: parsed.qty ?? "",
    price: parsed.price ?? "",
    executed_at: toLocalInputValue(parsed.executed_at),
    option_type: parsed.option_type ?? "call",
    strike: parsed.strike ?? "",
    expiry: parsed.expiry ?? "",
    multiplier: parsed.multiplier ?? 100,
    underlying_ticker: parsed.underlying_ticker ?? "",
  });
  const [error, setError] = useState(null);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const accountUnmatched =
    !parseData.account_id && parsed.account_name && (accounts ?? []).length > 0;

  const isOption = form.instrument_type === "option";

  const handleSubmit = async () => {
    setError(null);
    try {
      const result = await commitMutation.mutateAsync({
        account_id: form.account_id,
        ticker: form.ticker,
        instrument_type: form.instrument_type,
        side: form.side,
        qty: String(form.qty),
        price: String(form.price),
        executed_at: new Date(form.executed_at).toISOString(),
        ...(isOption
          ? {
              option_type: form.option_type,
              strike: form.strike !== "" ? String(form.strike) : undefined,
              expiry: form.expiry || undefined,
              multiplier: form.multiplier ? Number(form.multiplier) : undefined,
              underlying_ticker: form.underlying_ticker || undefined,
            }
          : {}),
      });
      onCommit?.(result.warnings ?? []);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Account strip */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wide mb-1">
          Account *
        </label>
        <select
          value={form.account_id}
          onChange={set("account_id")}
          className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
        >
          <option value="">— select account —</option>
          {(accounts ?? []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.account_type ? ` (${a.account_type})` : ""}
            </option>
          ))}
        </select>
        {accountUnmatched && (
          <p className="mt-1 text-xs font-mono text-amber-800">
            Parsed account "{parsed.account_name}" doesn't match a known account
            — pick one above. (New accounts are created via snapshot upload.)
          </p>
        )}
      </div>

      {/* Fill fields */}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">Ticker *</label>
          <input
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
            onChange={set("side")}
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
            onChange={set("instrument_type")}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
          >
            <option value="equity">Equity</option>
            <option value="option">Option</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">Qty *</label>
          <input
            type="number"
            step="any"
            min="0"
            value={form.qty}
            onChange={set("qty")}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            placeholder="10"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">Price *</label>
          <input
            type="number"
            step="any"
            min="0"
            value={form.price}
            onChange={set("price")}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            placeholder="190.00"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">Executed At *</label>
          <input
            type="datetime-local"
            value={form.executed_at}
            onChange={set("executed_at")}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
          />
        </div>
      </div>

      {/* Option leg fields */}
      {isOption && (
        <div className="grid grid-cols-4 gap-3 border-2 border-ink/30 p-3 bg-cream/50">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Call/Put</label>
            <select
              value={form.option_type}
              onChange={set("option_type")}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            >
              <option value="call">Call</option>
              <option value="put">Put</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Strike</label>
            <input
              type="number"
              step="any"
              value={form.strike}
              onChange={set("strike")}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="480"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Expiry</label>
            <input
              type="date"
              value={form.expiry}
              onChange={set("expiry")}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide mb-1">Multiplier</label>
            <input
              type="number"
              value={form.multiplier}
              onChange={set("multiplier")}
              className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
              placeholder="100"
            />
          </div>
        </div>
      )}

      {error && (
        <p className="text-red-600 text-sm font-mono border border-red-300 p-2">{error}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={
            commitMutation.isPending ||
            !form.account_id ||
            !form.ticker ||
            !form.qty ||
            form.price === ""
          }
          className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink bg-ink text-warm-white hover:bg-dark-brown disabled:opacity-50"
        >
          {commitMutation.isPending ? "Saving…" : "Commit Trade"}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink hover:bg-cream"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
