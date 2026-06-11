import { useRef, useState } from "react";
import { parseSnapshot, parseTrade } from "../../api/portfolio";
import SnapshotReviewPane from "./SnapshotReviewPane";
import TradeReviewPane from "./TradeReviewPane";

const MODES = {
  snapshot: {
    title: "Upload Portfolio Snapshot",
    dropPrompt: "Drop a portfolio screenshot here, or",
    loadingDetail: "Gemini is reading your portfolio positions.",
    doneLabel: "Snapshot committed ✓",
  },
  trade: {
    title: "Upload Trade Confirmation",
    dropPrompt: "Drop a trade-confirmation screenshot here, or",
    loadingDetail: "Gemini is reading your trade confirmation.",
    doneLabel: "Trade committed ✓",
  },
};

function DropZone({ prompt, onFile }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer border-4 border-dashed p-12 text-center transition-colors ${
        dragging
          ? "border-accent bg-cream"
          : "border-ink/30 hover:border-ink/60 hover:bg-cream/50"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { const f = e.target.files[0]; if (f) onFile(f); }}
      />
      <p className="font-mono text-sm text-mid-brown">
        {prompt}{" "}
        <span className="underline text-ink">click to select</span>
      </p>
      <p className="font-mono text-xs text-mid-brown mt-1">PNG, JPG, or WebP</p>
    </div>
  );
}

function ModeToggle({ mode, onSelect }) {
  return (
    <div className="flex border-2 border-ink mb-4">
      {[
        ["snapshot", "Portfolio Snapshot"],
        ["trade", "Trade Confirmation"],
      ].map(([value, label]) => (
        <button
          key={value}
          onClick={() => onSelect(value)}
          className={`flex-1 px-3 py-2 text-xs font-mono uppercase tracking-wide ${
            mode === value
              ? "bg-ink text-warm-white"
              : "bg-warm-white text-ink hover:bg-cream"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default function UploadReviewModal({ onClose }) {
  const [mode, setMode] = useState(
    () => localStorage.getItem("uploadReviewMode") || "snapshot"
  );
  const [stage, setStage] = useState("upload"); // "upload" | "loading" | "review" | "done"
  const [parseData, setParseData] = useState(null);
  const [parseError, setParseError] = useState(null);
  const [commitWarnings, setCommitWarnings] = useState([]);

  const modeCopy = MODES[mode];

  const selectMode = (value) => {
    setMode(value);
    localStorage.setItem("uploadReviewMode", value);
  };

  const handleFile = async (file) => {
    setParseError(null);
    setStage("loading");
    try {
      const formData = new FormData();
      formData.append("image", file);
      const data =
        mode === "trade" ? await parseTrade(formData) : await parseSnapshot(formData);
      setParseData(data);
      setStage("review");
    } catch (err) {
      setParseError(err.message);
      setStage("upload");
    }
  };

  const handleCommit = (warnings = []) => {
    setCommitWarnings(warnings);
    setStage("done");
    if (warnings.length === 0) setTimeout(onClose, 800);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="fixed inset-0 bg-ink/40" />
      <div className="relative z-10 bg-warm-white border-4 border-ink shadow-hard w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-ink">
          <h2 className="font-serif font-bold text-xl">{modeCopy.title}</h2>
          <button
            onClick={onClose}
            className="font-mono text-lg leading-none px-2 py-1 hover:bg-cream border border-ink"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-6">
          {stage === "upload" && (
            <>
              <ModeToggle mode={mode} onSelect={selectMode} />
              <DropZone prompt={modeCopy.dropPrompt} onFile={handleFile} />
              {parseError && (
                <p className="mt-3 text-red-600 text-sm font-mono border border-red-300 p-2">
                  {parseError}
                </p>
              )}
            </>
          )}

          {stage === "loading" && (
            <div className="py-16 text-center font-mono text-mid-brown">
              <p className="text-lg mb-2">Parsing screenshot…</p>
              <p className="text-xs">{modeCopy.loadingDetail}</p>
            </div>
          )}

          {stage === "review" && parseData && mode === "snapshot" && (
            <SnapshotReviewPane
              diffData={parseData}
              onCommit={handleCommit}
              onCancel={onClose}
            />
          )}

          {stage === "review" && parseData && mode === "trade" && (
            <TradeReviewPane
              parseData={parseData}
              onCommit={handleCommit}
              onCancel={onClose}
            />
          )}

          {stage === "done" && (
            <div className="py-16 text-center font-mono">
              <p className="text-lg font-bold text-green-700">{modeCopy.doneLabel}</p>
              {commitWarnings.length > 0 && (
                <div className="mt-4 mx-auto max-w-md p-2 border border-amber-400 bg-amber-50 text-amber-800 text-xs text-left">
                  {commitWarnings.map((w, i) => (
                    <div key={i}>⚠ {w}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
