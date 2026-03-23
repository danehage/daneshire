import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useUpdateWatchlistItem,
  useDeleteWatchlistItem,
} from "../hooks/useWatchlist";
import PriceTargets from "./PriceTargets";
import JournalEntries from "./JournalEntries";

const STATUS_LABELS = {
  watching: "Watching",
  position_open: "Open",
  closed: "Closed",
};

const STATUS_COLORS = {
  watching: "bg-warm-white text-dark-brown border-ink",
  position_open: "bg-success text-warm-white border-ink",
  closed: "bg-light-brown text-warm-white border-ink",
};

export default function WatchlistRow({ item, dragHandleProps }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editStatus, setEditStatus] = useState(item.status);
  const updateItem = useUpdateWatchlistItem();
  const deleteItem = useDeleteWatchlistItem();

  const handleStatusChange = (newStatus) => {
    setEditStatus(newStatus);
    updateItem.mutate(
      { id: item.id, data: { status: newStatus } },
      { onSuccess: () => setIsEditing(false) }
    );
  };

  const handleDelete = () => {
    if (confirm(`Remove ${item.ticker} from watchlist?`)) {
      deleteItem.mutate(item.id);
    }
  };

  return (
    <>
      <tr
        className={`border-b-2 border-ink hover:bg-warm-white transition-colors cursor-pointer ${
          isExpanded ? "bg-warm-white" : ""
        }`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <td className="py-4 px-4" onClick={(e) => e.stopPropagation()}>
          <span
            {...dragHandleProps}
            className="cursor-grab text-light-brown hover:text-ink transition-colors text-lg"
          >
            ⋮⋮
          </span>
        </td>
        <td className="py-4 px-4">
          <div className="flex items-center gap-2">
            <span
              className={`text-xs transition-transform ${
                isExpanded ? "rotate-90" : ""
              }`}
            >
              ▶
            </span>
            <Link
              to={`/ticker/${item.ticker}`}
              onClick={(e) => e.stopPropagation()}
              className="font-serif text-lg text-ink hover:text-accent transition-colors"
            >
              {item.ticker}
            </Link>
          </div>
        </td>
        <td className="py-4 px-4" onClick={(e) => e.stopPropagation()}>
          {isEditing ? (
            <select
              value={editStatus}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="text-xs px-2 py-1 border-2 border-ink bg-warm-white uppercase tracking-wide"
            >
              <option value="watching">Watching</option>
              <option value="position_open">Open</option>
              <option value="closed">Closed</option>
            </select>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className={`text-xs px-3 py-1 border-2 uppercase tracking-wide font-medium ${STATUS_COLORS[item.status]}`}
            >
              {STATUS_LABELS[item.status]}
            </button>
          )}
        </td>
        <td className="py-4 px-4 text-mid-brown font-sans">
          {item.entry_price
            ? `$${parseFloat(item.entry_price).toFixed(2)}`
            : "—"}
        </td>
        <td className="py-4 px-4">
          {item.tags && item.tags.length > 0 ? (
            <div className="flex gap-2 flex-wrap">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-1 bg-cream border border-light-brown text-dark-brown"
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-light-brown">—</span>
          )}
        </td>
        <td className="py-4 px-4 text-right" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={handleDelete}
            disabled={deleteItem.isPending}
            className="text-light-brown hover:text-error font-bold text-lg transition-colors"
          >
            {deleteItem.isPending ? "..." : "×"}
          </button>
        </td>
      </tr>
      {isExpanded && (
        <tr className="bg-cream border-b-2 border-ink">
          <td colSpan={6} className="px-8 py-4">
            <div className="grid grid-cols-2 gap-8">
              <PriceTargets watchlistId={item.id} ticker={item.ticker} />
              <JournalEntries watchlistId={item.id} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
