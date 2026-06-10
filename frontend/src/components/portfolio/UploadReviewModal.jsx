import { useRef, useState } from "react";
import { parseSnapshot } from "../../api/portfolio";
import SnapshotReviewPane from "./SnapshotReviewPane";

function DropZone({ onFile }) {
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
        Drop a portfolio screenshot here, or{" "}
        <span className="underline text-ink">click to select</span>
      </p>
      <p className="font-mono text-xs text-mid-brown mt-1">PNG, JPG, or WebP</p>
    </div>
  );
}

export default function UploadReviewModal({ onClose }) {
  const [stage, setStage] = useState("upload"); // "upload" | "loading" | "review" | "done"
  const [diffData, setDiffData] = useState(null);
  const [parseError, setParseError] = useState(null);

  const handleFile = async (file) => {
    setParseError(null);
    setStage("loading");
    try {
      const formData = new FormData();
      formData.append("image", file);
      const data = await parseSnapshot(formData);
      setDiffData(data);
      setStage("review");
    } catch (err) {
      setParseError(err.message);
      setStage("upload");
    }
  };

  const handleCommit = () => {
    setStage("done");
    setTimeout(onClose, 800);
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
          <h2 className="font-serif font-bold text-xl">Upload Portfolio Snapshot</h2>
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
              <DropZone onFile={handleFile} />
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
              <p className="text-xs">Gemini is reading your portfolio positions.</p>
            </div>
          )}

          {stage === "review" && diffData && (
            <SnapshotReviewPane
              diffData={diffData}
              onCommit={handleCommit}
              onCancel={onClose}
            />
          )}

          {stage === "done" && (
            <div className="py-16 text-center font-mono text-green-700">
              <p className="text-lg font-bold">Snapshot committed ✓</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
