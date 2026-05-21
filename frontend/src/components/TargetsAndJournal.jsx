import PriceTargets from "./PriceTargets";
import JournalEntries from "./JournalEntries";

export default function TargetsAndJournal({ watchlistId, ticker }) {
  return (
    <div className="grid grid-cols-2 gap-8">
      <PriceTargets watchlistId={watchlistId} ticker={ticker} />
      <JournalEntries watchlistId={watchlistId} />
    </div>
  );
}
