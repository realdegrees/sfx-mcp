import { Check, MessageSquare, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { type Candidate, type Review, type Slot, api } from "../lib/api";

function NoteEditor({
  initial,
  onSave,
  onClose,
}: { initial: string; onSave: (note: string) => void; onClose: () => void }) {
  const [note, setNote] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  const commit = () => {
    if (note !== initial) onSave(note.trim());
    onClose();
  };

  return (
    <textarea
      ref={ref}
      value={note}
      onChange={(e) => setNote(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          commit();
        }
      }}
      placeholder="What to change, or where a problem is. Enter saves, Esc cancels."
      rows={3}
      className="mt-3 w-full rounded border border-zinc-600 bg-zinc-950 px-2 py-1 text-sm"
    />
  );
}

function CandidateCard({ candidate, onSaved }: { candidate: Candidate; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const { status, note } = candidate.review;

  const save = (review: Review) =>
    api
      .review(candidate.name, review)
      .then(onSaved)
      .catch((e: Error) => setError(e.message));

  const frame =
    status === "picked"
      ? "border-emerald-600 bg-emerald-950/40"
      : status === "rejected"
        ? "border-zinc-800 bg-zinc-900/60 opacity-50 hover:opacity-80"
        : "border-zinc-800 bg-zinc-900";

  const toggle = (next: "picked" | "rejected") => save({ status: status === next ? null : next, note });

  return (
    <li className={`flex flex-col rounded-lg border p-4 ${frame}`} data-testid={`candidate-${candidate.name}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-semibold">{candidate.name}</div>
          <div className="mt-0.5 flex gap-3 text-xs text-zinc-500">
            {candidate.duration !== null && <span>{candidate.duration.toFixed(1)}s</span>}
            {candidate.source && <span>{candidate.source}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={() => toggle("picked")}
            title="Pick"
            aria-label="Pick"
            className={`rounded p-1.5 ${status === "picked" ? "bg-emerald-600 text-white" : "text-zinc-400 hover:bg-zinc-800 hover:text-white"}`}
          >
            <Check size={16} />
          </button>
          <button
            type="button"
            onClick={() => toggle("rejected")}
            title="Reject"
            aria-label="Reject"
            className={`rounded p-1.5 ${status === "rejected" ? "bg-red-700 text-white" : "text-zinc-400 hover:bg-zinc-800 hover:text-white"}`}
          >
            <X size={16} />
          </button>
          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            title={note ? "Edit note" : "Add note"}
            aria-label={note ? "Edit note" : "Add note"}
            className={`rounded p-1.5 ${note || editing ? "text-amber-300" : "text-zinc-400"} hover:bg-zinc-800 hover:text-white`}
          >
            <MessageSquare size={16} />
          </button>
        </div>
      </div>
      {candidate.description && (
        <p className="mt-2 flex-1 text-sm leading-snug text-zinc-300">{candidate.description}</p>
      )}
      {note && !editing && (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="mt-2 rounded border-l-2 border-amber-400 bg-zinc-950/60 px-2 py-1 text-left text-xs text-amber-200"
        >
          {note}
        </button>
      )}
      {editing && (
        <NoteEditor initial={note} onSave={(next) => save({ status, note: next })} onClose={() => setEditing(false)} />
      )}
      <audio
        controls
        preload="none"
        src={`/api/renders/${encodeURIComponent(candidate.name)}/file?v=${candidate.modified}`}
        className="mt-3 h-9 w-full"
      />
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </li>
  );
}

export default function ReviewBoard({
  slots,
  onSaved,
  compact = false,
}: { slots: Slot[]; onSaved: () => void; compact?: boolean }) {
  return (
    <div className="mt-4 space-y-10" data-testid="review-board">
      {slots.map((slot) => {
        const picked = slot.candidates.filter((c) => c.review.status === "picked").map((c) => c.name);
        return (
          <section key={slot.key}>
            <div className="flex flex-wrap items-baseline gap-3 border-b border-zinc-800 pb-2">
              <h3 className="text-base font-semibold">{slot.title}</h3>
              <span className="text-xs text-zinc-500">
                {slot.candidates.length}{" "}
                {compact ? "picked" : slot.candidates.length === 1 ? "candidate" : "candidates"}
              </span>
              {!compact && picked.length > 0 && (
                <span className="text-xs text-emerald-400">Picked: {picked.join(", ")}</span>
              )}
            </div>
            <div className="mt-2 grid gap-x-8 gap-y-1 text-sm text-zinc-400 lg:grid-cols-[1fr_auto]">
              {slot.use && <p className="max-w-3xl">{slot.use}</p>}
              {!compact && slot.pick && <p className="text-zinc-500 lg:text-right">{slot.pick}</p>}
            </div>
            {slot.candidates.length === 0 ? (
              <p className="mt-3 text-sm text-zinc-500">No candidates rendered yet.</p>
            ) : (
              <ul className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {slot.candidates.map((c) => (
                  <CandidateCard key={`${c.name}-${c.modified}`} candidate={c} onSaved={onSaved} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
