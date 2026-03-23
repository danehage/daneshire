import { useState } from "react";
import {
  usePriceTargets,
  useCreatePriceTarget,
  useDeletePriceTarget,
} from "../hooks/usePriceTargets";

const DIRECTION_LABELS = {
  above: "Above",
  below: "Below",
};

function AddTargetForm({ watchlistId, onClose }) {
  const [label, setLabel] = useState("");
  const [price, setPrice] = useState("");
  const [direction, setDirection] = useState("below");
  const createTarget = useCreatePriceTarget(watchlistId);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!label.trim() || !price) return;

    createTarget.mutate(
      { label: label.trim(), price, direction },
      { onSuccess: onClose }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end mt-3">
      <div>
        <label className="block text-xs text-mid-brown uppercase tracking-wide mb-1">
          Label
        </label>
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Stop loss"
          className="px-3 py-2 border-2 border-ink bg-warm-white text-sm w-32"
        />
      </div>
      <div>
        <label className="block text-xs text-mid-brown uppercase tracking-wide mb-1">
          Price
        </label>
        <input
          type="number"
          step="0.01"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="150.00"
          className="px-3 py-2 border-2 border-ink bg-warm-white text-sm w-28"
        />
      </div>
      <div>
        <label className="block text-xs text-mid-brown uppercase tracking-wide mb-1">
          Direction
        </label>
        <select
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          className="px-3 py-2 border-2 border-ink bg-warm-white text-sm"
        >
          <option value="below">Below</option>
          <option value="above">Above</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={createTarget.isPending}
        className="px-4 py-2 bg-accent text-warm-white text-sm font-medium uppercase tracking-wide border-2 border-ink shadow-hard-sm hover:bg-accent-hover disabled:opacity-50"
      >
        {createTarget.isPending ? "..." : "Add"}
      </button>
      <button
        type="button"
        onClick={onClose}
        className="px-3 py-2 text-mid-brown hover:text-ink text-sm"
      >
        Cancel
      </button>
    </form>
  );
}

export default function PriceTargets({ watchlistId, ticker }) {
  const [showForm, setShowForm] = useState(false);
  const { data: targets, isLoading } = usePriceTargets(watchlistId);
  const deleteTarget = useDeletePriceTarget(watchlistId);

  if (isLoading) {
    return <div className="text-sm text-mid-brown py-2">Loading targets...</div>;
  }

  return (
    <div className="py-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown">
          Price Targets
        </h4>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="text-xs text-accent hover:text-accent-hover font-medium uppercase tracking-wide"
          >
            + Add
          </button>
        )}
      </div>

      {targets && targets.length > 0 ? (
        <div className="space-y-2">
          {targets.map((target) => (
            <div
              key={target.id}
              className="flex items-center justify-between py-2 px-3 bg-cream border border-light-brown"
            >
              <div className="flex items-center gap-4">
                <span className="font-medium text-ink">{target.label}</span>
                <span className="text-mid-brown">
                  ${parseFloat(target.price).toFixed(2)}
                </span>
                <span className="text-xs px-2 py-0.5 bg-warm-white border border-ink text-dark-brown uppercase">
                  {DIRECTION_LABELS[target.direction]}
                </span>
                {target.triggered_at && (
                  <span className="text-xs text-success">Triggered</span>
                )}
              </div>
              <button
                onClick={() => deleteTarget.mutate(target.id)}
                disabled={deleteTarget.isPending}
                className="text-light-brown hover:text-error font-bold"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-light-brown italic">No price targets set</p>
      )}

      {showForm && (
        <AddTargetForm
          watchlistId={watchlistId}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  );
}
