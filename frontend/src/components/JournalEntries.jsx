import { useState } from "react";
import {
  useJournalEntries,
  useCreateJournalEntry,
  useDeleteJournalEntry,
} from "../hooks/useJournal";

const ENTRY_TYPES = [
  { value: "thesis", label: "Thesis" },
  { value: "note", label: "Note" },
  { value: "entry", label: "Entry" },
  { value: "exit", label: "Exit" },
  { value: "adjustment", label: "Adjustment" },
  { value: "review", label: "Review" },
];

const TYPE_COLORS = {
  thesis: "bg-accent text-warm-white",
  note: "bg-warm-white text-dark-brown",
  entry: "bg-success text-warm-white",
  exit: "bg-error text-warm-white",
  adjustment: "bg-warning text-warm-white",
  review: "bg-light-brown text-warm-white",
};

function AddEntryForm({ watchlistId, onClose }) {
  const [entryType, setEntryType] = useState("note");
  const [content, setContent] = useState("");
  const createEntry = useCreateJournalEntry(watchlistId);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!content.trim()) return;

    createEntry.mutate(
      { entry_type: entryType, content: content.trim() },
      {
        onSuccess: () => {
          setContent("");
          onClose();
        },
      }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3 space-y-3">
      <div className="flex gap-2">
        <select
          value={entryType}
          onChange={(e) => setEntryType(e.target.value)}
          className="px-3 py-2 border-2 border-ink bg-warm-white text-sm"
        >
          {ENTRY_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Write your notes here... (supports Markdown)"
        rows={4}
        className="w-full px-3 py-2 border-2 border-ink bg-warm-white text-sm font-serif resize-none"
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={createEntry.isPending || !content.trim()}
          className="px-4 py-2 bg-accent text-warm-white text-sm font-medium uppercase tracking-wide border-2 border-ink shadow-hard-sm hover:bg-accent-hover disabled:opacity-50"
        >
          {createEntry.isPending ? "Saving..." : "Save Entry"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-2 text-mid-brown hover:text-ink text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function JournalEntries({ watchlistId }) {
  const [showForm, setShowForm] = useState(false);
  const { data: entries, isLoading } = useJournalEntries(watchlistId);
  const deleteEntry = useDeleteJournalEntry(watchlistId);

  if (isLoading) {
    return <div className="text-sm text-mid-brown py-2">Loading journal...</div>;
  }

  return (
    <div className="py-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-dark-brown">
          Journal
        </h4>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="text-xs text-accent hover:text-accent-hover font-medium uppercase tracking-wide"
          >
            + Add Entry
          </button>
        )}
      </div>

      {showForm && (
        <AddEntryForm
          watchlistId={watchlistId}
          onClose={() => setShowForm(false)}
        />
      )}

      {entries && entries.length > 0 ? (
        <div className="space-y-3 mt-3">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="py-3 px-4 bg-cream border border-light-brown"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs px-2 py-0.5 border border-ink uppercase tracking-wide ${
                      TYPE_COLORS[entry.entry_type]
                    }`}
                  >
                    {entry.entry_type}
                  </span>
                  <span className="text-xs text-light-brown">
                    {formatDate(entry.created_at)}
                  </span>
                </div>
                <button
                  onClick={() => deleteEntry.mutate(entry.id)}
                  disabled={deleteEntry.isPending}
                  className="text-light-brown hover:text-error font-bold"
                >
                  ×
                </button>
              </div>
              <p className="text-sm text-ink font-serif whitespace-pre-wrap">
                {entry.content}
              </p>
            </div>
          ))}
        </div>
      ) : (
        !showForm && (
          <p className="text-sm text-light-brown italic">No journal entries yet</p>
        )
      )}
    </div>
  );
}
