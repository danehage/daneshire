import { useState } from 'react';
import { useCreateEarningsTrade } from '../hooks/useEarnings';

const EMPTY = {
  ticker: '',
  earnings_event_id: '',
  structure: 'iron_condor',
  is_paper: true,
  entry_date: new Date().toISOString().slice(0, 10),
  expiry_date: '',
  short_put_strike: '',
  long_put_strike: '',
  short_call_strike: '',
  long_call_strike: '',
  entry_credit: '',
  contracts: 1,
  commissions: '0',
  notes: '',
};

export default function EarningsTradeForm({ earningsEvents = [] }) {
  const [form, setForm] = useState(EMPTY);
  const create = useCreateEarningsTrade();

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function handleEventChange(eventId) {
    const ev = earningsEvents.find((e) => e.id === eventId);
    setForm((f) => ({
      ...f,
      earnings_event_id: eventId,
      ticker: ev ? ev.ticker : f.ticker,
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        ...form,
        contracts: Number(form.contracts),
      });
      setForm(EMPTY);
    } catch (err) {
      // Mutation error is surfaced via create.error; nothing else to do.
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-2 border-ink p-4 space-y-3">
      <h3 className="font-serif font-bold text-lg text-ink">Log new earnings trade</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="text-sm">
          <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            Earnings event
          </span>
          <select
            value={form.earnings_event_id}
            onChange={(e) => handleEventChange(e.target.value)}
            required
            className="w-full border-2 border-ink px-2 py-1 bg-warm-white"
          >
            <option value="">— select —</option>
            {earningsEvents.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.ticker} · {ev.report_date} · {ev.report_time?.toUpperCase()}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            Ticker
          </span>
          <input
            type="text"
            value={form.ticker}
            onChange={(e) => update('ticker', e.target.value.toUpperCase())}
            required
            maxLength={10}
            className="w-full border-2 border-ink px-2 py-1 font-mono bg-warm-white"
          />
        </label>

        <label className="text-sm">
          <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            Structure
          </span>
          <select
            value={form.structure}
            onChange={(e) => update('structure', e.target.value)}
            className="w-full border-2 border-ink px-2 py-1 bg-warm-white"
          >
            <option value="iron_condor">Iron condor</option>
            <option value="iron_butterfly">Iron butterfly</option>
          </select>
        </label>

        <label className="text-sm flex items-center gap-2 mt-5">
          <input
            type="checkbox"
            checked={form.is_paper}
            onChange={(e) => update('is_paper', e.target.checked)}
          />
          <span className="text-mid-brown">Paper trade</span>
        </label>

        <label className="text-sm">
          <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            Entry date
          </span>
          <input
            type="date"
            value={form.entry_date}
            onChange={(e) => update('entry_date', e.target.value)}
            required
            className="w-full border-2 border-ink px-2 py-1 bg-warm-white"
          />
        </label>

        <label className="text-sm">
          <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
            Expiry date
          </span>
          <input
            type="date"
            value={form.expiry_date}
            onChange={(e) => update('expiry_date', e.target.value)}
            required
            className="w-full border-2 border-ink px-2 py-1 bg-warm-white"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <NumberField label="Long put" value={form.long_put_strike} onChange={(v) => update('long_put_strike', v)} />
        <NumberField label="Short put" value={form.short_put_strike} onChange={(v) => update('short_put_strike', v)} />
        <NumberField label="Short call" value={form.short_call_strike} onChange={(v) => update('short_call_strike', v)} />
        <NumberField label="Long call" value={form.long_call_strike} onChange={(v) => update('long_call_strike', v)} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <NumberField label="Entry credit" value={form.entry_credit} onChange={(v) => update('entry_credit', v)} step="0.01" />
        <NumberField label="Contracts" value={form.contracts} onChange={(v) => update('contracts', v)} step="1" min="1" />
        <NumberField label="Commissions" value={form.commissions} onChange={(v) => update('commissions', v)} step="0.01" />
      </div>

      <label className="text-sm block">
        <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
          Notes
        </span>
        <textarea
          value={form.notes}
          onChange={(e) => update('notes', e.target.value)}
          rows={2}
          className="w-full border-2 border-ink px-2 py-1 bg-warm-white"
        />
      </label>

      {create.isError && (
        <div className="border-2 border-red-500 bg-red-50 p-2 text-red-700 text-xs">
          {create.error?.message}
        </div>
      )}

      <button
        type="submit"
        disabled={create.isPending}
        className="border-2 border-ink bg-ink text-warm-white px-4 py-2 text-sm font-bold uppercase tracking-wide hover:bg-mid-brown disabled:opacity-50"
      >
        {create.isPending ? 'Saving…' : 'Log trade'}
      </button>
    </form>
  );
}

function NumberField({ label, value, onChange, step = '0.01', min }) {
  return (
    <label className="text-sm">
      <span className="block text-xs font-semibold uppercase tracking-wide text-mid-brown mb-1">
        {label}
      </span>
      <input
        type="number"
        step={step}
        min={min}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        className="w-full border-2 border-ink px-2 py-1 font-mono bg-warm-white"
      />
    </label>
  );
}
