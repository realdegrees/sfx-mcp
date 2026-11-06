import { Check, CheckCheck, Wrench, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { type Candidate, type Review, type Slot, api } from "../lib/api";

function ModifyEditor({
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
    if (note.trim() !== initial) onSave(note.trim());
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
      placeholder="What should the agent change? Enter saves, Esc cancels, an empty note withdraws the request."
      rows={3}
      className="mt-3 w-full rounded border border-amber-600/60 bg-zinc-950 px-2 py-1 text-sm"
    />
  );
}

function IconButton({
  active,
  activeClass,
  title,
  onClick,
  children,
}: {
  active: boolean;
  activeClass: string;
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className={`rounded p-1.5 ${active ? activeClass : "text-zinc-400 hover:bg-zinc-800 hover:text-white"}`}
    >
      {children}
    </button>
  );
}

function CandidateCard({
  candidate,
  onSaved,
  compact,
}: { candidate: Candidate; onSaved: () => void; compact: boolean }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const { status, note } = candidate.review;

  const save = (review: Review) =>
    api
      .review(candidate.name, review)
      .then(() => {
        setError("");
        onSaved();
      })
      .catch((e: Error) => setError(e.message));

  const decided = !compact && (status === "picked" || status === "rejected");
  const frame =
    status === "picked"
      ? "border-emerald-600 bg-emerald-950/40"
      : status === "modify"
        ? "border-amber-600/70 bg-amber-950/20"
        : status === "rejected"
          ? "border-red-900/60 bg-zinc-900/60"
          : "border-zinc-800 bg-zinc-900";
  const fade = decided ? "opacity-40 saturate-50 transition hover:opacity-90 hover:saturate-100" : "";

  const toggle = (next: "picked" | "rejected") => save({ status: status === next ? null : next, note: "" });

  return (
    <li className={`flex flex-col rounded-lg border p-4 ${frame} ${fade}`} data-testid={`candidate-${candidate.name}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-semibold">{candidate.name}</div>
          <div className="mt-0.5 flex gap-3 text-xs text-zinc-500">
            {candidate.duration !== null && <span>{candidate.duration.toFixed(1)}s</span>}
            {candidate.source && <span>{candidate.source}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <IconButton
            active={status === "picked"}
            activeClass="bg-emerald-600 text-white"
            title="Pick"
            onClick={() => toggle("picked")}
          >
            <Check size={16} />
          </IconButton>
          <IconButton
            active={status === "modify" || editing}
            activeClass="bg-amber-600 text-white"
            title="Ask the agent to modify"
            onClick={() => setEditing((v) => !v)}
          >
            <Wrench size={16} />
          </IconButton>
          <IconButton
            active={status === "rejected"}
            activeClass="bg-red-700 text-white"
            title="Reject"
            onClick={() => toggle("rejected")}
          >
            <X size={16} />
          </IconButton>
        </div>
      </div>
      {candidate.description && (
        <p className="mt-2 flex-1 text-sm leading-snug text-zinc-300">{candidate.description}</p>
      )}
      {candidate.revised && (
        <p className="mt-2 rounded border-l-2 border-sky-400 bg-zinc-950/60 px-2 py-1 text-xs text-sky-200">
          Revised: {candidate.revised}
        </p>
      )}
      {status === "modify" && !editing && (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="mt-2 rounded border-l-2 border-amber-400 bg-zinc-950/60 px-2 py-1 text-left text-xs text-amber-200"
        >
          Change: {note}
        </button>
      )}
      {editing && (
        <ModifyEditor
          initial={status === "modify" ? note : ""}
          onSave={(next) =>
            save(next ? { status: "modify", note: next } : { status: status === "modify" ? null : status, note: "" })
          }
          onClose={() => setEditing(false)}
        />
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
        const pending = slot.candidates.filter((c) => c.review.status === null).length;
        return (
          <section key={slot.key}>
            <div className="flex flex-wrap items-center gap-3 border-b border-zinc-800 pb-2">
              <h3 className="text-base font-semibold">{slot.title}</h3>
              {compact && slot.round && <span className="text-xs text-zinc-500">{slot.round}</span>}
              <span className="text-xs text-zinc-500">
                {slot.candidates.length}{" "}
                {compact ? "picked" : slot.candidates.length === 1 ? "candidate" : "candidates"}
              </span>
              {!compact && pending > 0 && (
                <button
                  type="button"
                  onClick={() => api.pickRemaining(slot.key).then(onSaved)}
                  className="ml-auto flex items-center gap-1 rounded px-2 py-1 text-xs text-emerald-300 hover:bg-zinc-800"
                >
                  <CheckCheck size={14} /> Pick remaining ({pending})
                </button>
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
                  <CandidateCard key={`${c.name}-${c.modified}`} candidate={c} onSaved={onSaved} compact={compact} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
