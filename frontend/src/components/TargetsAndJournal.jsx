import PriceTargets from "./PriceTargets";
import JournalEntries from "./JournalEntries";

export default function TargetsAndJournal({ watchlistId, ticker }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
        <PriceTargets watchlistId={watchlistId} ticker={ticker} />
      </div>
      <div className="border-2 border-ink shadow-hard bg-warm-white p-6">
        <JournalEntries watchlistId={watchlistId} />
      </div>
    </div>
  );
}
