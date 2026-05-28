import { useState } from "react";
import { useAccounts, useCommitSnapshot } from "../../hooks/usePortfolio";

function DiffBadge({ status }) {
  const styles = {
    new: "bg-green-100 text-green-800 border-green-300",
    changed: "bg-amber-100 text-amber-800 border-amber-300",
    removed: "bg-red-100 text-red-800 border-red-300",
    unchanged: "bg-gray-100 text-gray-600 border-gray-300",
  };
  return (
    <span
      className={`px-1.5 py-0.5 text-xs font-mono border uppercase ${styles[status] ?? styles.unchanged}`}
    >
      {status}
    </span>
  );
}

export default function SnapshotReviewPane({ diffData, onCommit, onCancel }) {
  const { data: accounts } = useAccounts();
  const commitMutation = useCommitSnapshot();

  const parsed = diffData.parsed_snapshot;

  const [accountName, setAccountName] = useState(parsed.account_name ?? "");
  const [accountType, setAccountType] = useState(parsed.account_type ?? "");
  const [capturedAt, setCapturedAt] = useState(
    parsed.captured_at
      ? new Date(parsed.captured_at).toISOString().slice(0, 16)
      : new Date().toISOString().slice(0, 16)
  );
  const [cashBalance, setCashBalance] = useState(parsed.cash_balance ?? "");
  const [totalValue, setTotalValue] = useState(parsed.parsed_total_value ?? "");

  const [positions, setPositions] = useState(
    parsed.positions.map((p) => ({ ...p }))
  );
  const [error, setError] = useState(null);

  const diffByTicker = {};
  for (const d of diffData.position_diffs) {
    diffByTicker[d.ticker] = d;
  }

  const removedPositions = diffData.position_diffs.filter(
    (d) => d.status === "removed"
  );

  const handlePositionChange = (idx, field, value) => {
    setPositions((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const handleSubmit = async () => {
    setError(null);
    try {
      await commitMutation.mutateAsync({
        account_name: accountName,
        account_type: accountType || undefined,
        captured_at: new Date(capturedAt).toISOString(),
        cash_balance: cashBalance || undefined,
        total_value: totalValue || undefined,
        positions: positions.map((p) => ({
          instrument_type: p.instrument_type,
          ticker: p.ticker,
          qty: String(p.qty),
          avg_cost: p.avg_cost != null ? String(p.avg_cost) : "0",
          market_value_at_snapshot:
            p.market_value != null ? String(p.market_value) : undefined,
          option_type: p.option_type ?? undefined,
          strike: p.strike != null ? String(p.strike) : undefined,
          expiry: p.expiry ?? undefined,
          multiplier: p.multiplier ?? undefined,
          underlying_ticker: p.underlying_ticker ?? undefined,
        })),
      });
      onCommit?.();
    } catch (err) {
      setError(err.message);
    }
  };

  const totalsMismatch =
    diffData.parsed_total_value != null &&
    diffData.computed_total_value != null &&
    !diffData.totals_match;

  return (
    <div className="space-y-6">
      {/* Account strip */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">
            Account Name *
          </label>
          <div className="flex gap-2">
            <select
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              className="flex-1 px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            >
              <option value="">— select or type below —</option>
              {(accounts ?? []).map((a) => (
                <option key={a.id} value={a.name}>
                  {a.name}
                  {a.account_type ? ` (${a.account_type})` : ""}
                </option>
              ))}
              {parsed.account_name &&
                !(accounts ?? []).some((a) => a.name === parsed.account_name) && (
                  <option value={parsed.account_name}>
                    ✦ Create: {parsed.account_name}
                  </option>
                )}
            </select>
          </div>
          <input
            value={accountName}
            onChange={(e) => setAccountName(e.target.value)}
            className="mt-1 w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            placeholder="Or type a new account name"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">
            Account Type
          </label>
          <input
            value={accountType}
            onChange={(e) => setAccountType(e.target.value)}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            placeholder="individual, roth, ira…"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">
            Captured At *
          </label>
          <input
            type="datetime-local"
            value={capturedAt}
            onChange={(e) => setCapturedAt(e.target.value)}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
          />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide mb-1">
            Cash Balance
          </label>
          <input
            type="number"
            step="0.01"
            value={cashBalance}
            onChange={(e) => setCashBalance(e.target.value)}
            className="w-full px-2 py-1 border-2 border-ink font-mono text-sm bg-cream"
            placeholder="5000.00"
          />
        </div>
      </div>

      {/* Totals strip */}
      <div className="flex gap-4 text-sm font-mono border-2 border-ink p-3 bg-cream">
        <span>
          Parsed total:{" "}
          <strong>
            {diffData.parsed_total_value != null
              ? `$${Number(diffData.parsed_total_value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
              : "—"}
          </strong>
        </span>
        <span>
          Computed before:{" "}
          <strong>
            {diffData.computed_total_value != null
              ? `$${Number(diffData.computed_total_value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
              : "—"}
          </strong>
        </span>
        {totalsMismatch && (
          <span className="ml-auto px-2 py-0.5 bg-amber-200 border border-amber-400 text-amber-900 text-xs uppercase font-bold">
            Totals mismatch
          </span>
        )}
      </div>

      {/* Positions grid */}
      <div>
        <h3 className="font-serif font-bold text-base mb-2">
          Parsed Positions
          <span className="ml-2 text-xs font-mono font-normal text-mid-brown">
            (edit inline before committing)
          </span>
        </h3>
        <table className="w-full text-sm font-mono border-2 border-ink">
          <thead>
            <tr className="border-b-2 border-ink bg-cream">
              <th className="text-left py-1.5 px-2 text-xs uppercase tracking-wide">Ticker</th>
              <th className="text-left py-1.5 px-2 text-xs uppercase tracking-wide">Type</th>
              <th className="text-right py-1.5 px-2 text-xs uppercase tracking-wide">Qty</th>
              <th className="text-right py-1.5 px-2 text-xs uppercase tracking-wide">Avg Cost</th>
              <th className="text-right py-1.5 px-2 text-xs uppercase tracking-wide">Mkt Value</th>
              <th className="py-1.5 px-2 text-xs uppercase tracking-wide">Diff</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos, idx) => {
              const diff = diffByTicker[pos.ticker?.toUpperCase()] ?? {};
              return (
                <tr key={idx} className="border-b border-ink/20">
                  <td className="py-1 px-1">
                    <input
                      value={pos.ticker}
                      onChange={(e) => handlePositionChange(idx, "ticker", e.target.value)}
                      className="w-20 px-1 border border-ink/30 font-mono text-sm bg-warm-white"
                    />
                  </td>
                  <td className="py-1 px-2 text-xs text-mid-brown">{pos.instrument_type}</td>
                  <td className="py-1 px-1 text-right">
                    <input
                      type="number"
                      step="any"
                      value={pos.qty}
                      onChange={(e) => handlePositionChange(idx, "qty", e.target.value)}
                      className="w-20 px-1 border border-ink/30 font-mono text-sm text-right bg-warm-white"
                    />
                  </td>
                  <td className="py-1 px-1 text-right">
                    <input
                      type="number"
                      step="any"
                      value={pos.avg_cost ?? ""}
                      onChange={(e) => handlePositionChange(idx, "avg_cost", e.target.value)}
                      className="w-24 px-1 border border-ink/30 font-mono text-sm text-right bg-warm-white"
                      placeholder="—"
                    />
                  </td>
                  <td className="py-1 px-1 text-right">
                    <input
                      type="number"
                      step="any"
                      value={pos.market_value ?? ""}
                      onChange={(e) => handlePositionChange(idx, "market_value", e.target.value)}
                      className="w-24 px-1 border border-ink/30 font-mono text-sm text-right bg-warm-white"
                      placeholder="—"
                    />
                  </td>
                  <td className="py-1 px-2">
                    <DiffBadge status={diff.status ?? "new"} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {removedPositions.length > 0 && (
          <div className="mt-2 text-xs font-mono text-mid-brown border border-ink/20 p-2 bg-cream">
            <span className="font-bold text-red-700">Removed from current holdings:</span>{" "}
            {removedPositions.map((d) => d.ticker).join(", ")}
          </div>
        )}
      </div>

      {error && (
        <p className="text-red-600 text-sm font-mono border border-red-300 p-2">{error}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={commitMutation.isPending || !accountName}
          className="px-4 py-2 text-sm font-medium uppercase tracking-wide border-2 border-ink bg-ink text-warm-white hover:bg-dark-brown disabled:opacity-50"
        >
          {commitMutation.isPending ? "Saving…" : "Commit Snapshot"}
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
