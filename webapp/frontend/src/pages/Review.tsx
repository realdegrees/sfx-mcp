import { useCallback, useEffect, useState } from "react";
import ReviewBoard from "../components/ReviewBoard";
import { type Render, type Slot, type Sound, api } from "../lib/api";

export default function Review() {
  const [sounds, setSounds] = useState<Sound[]>([]);
  const [renders, setRenders] = useState<Render[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [boardTitle, setBoardTitle] = useState("");
  const [tag, setTag] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    api
      .local(tag || undefined)
      .then((d) => setSounds(d.results))
      .catch((e: Error) => setError(e.message));
  }, [tag]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const loadBoard = useCallback(() => {
    api
      .board()
      .then((d) => {
        setSlots(d.slots);
        setBoardTitle(d.title);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const load = () => {
      api
        .renders()
        .then((d) => setRenders(d.results))
        .catch((e: Error) => setError(e.message));
      loadBoard();
    };
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [loadBoard]);

  const onBoard = new Set(slots.flatMap((s) => s.candidates.map((c) => c.name)));
  const others = renders.filter((r) => !onBoard.has(r.name));

  return (
    <div>
      <h1 className="text-xl font-bold" data-testid="review-title">
        Review
      </h1>
      <p className="mt-1 text-sm text-zinc-400">
        Everything the agent renders and downloads. Picked sounds also appear in the Library.
      </p>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {slots.length > 0 && (
        <>
          <h2 className="mt-6 text-lg font-semibold">{boardTitle || "Review"}</h2>
          <p className="mt-1 text-sm text-zinc-400">
            Candidates grouped by what they are for. Pick or reject each, and leave a note for anything to change.
          </p>
          <ReviewBoard slots={slots} onSaved={loadBoard} />
        </>
      )}
      <h2 className="mt-8 text-lg font-semibold">{slots.length > 0 ? "Other renders" : "Renders"}</h2>
      <p className="mt-1 text-sm text-zinc-400">Sounds the agent designed. Refreshes by itself.</p>
      {others.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-500">No renders yet.</p>
      ) : (
        <ul
          className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
          data-testid="render-list"
        >
          {others.map((r) => (
            <li key={r.name} className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-baseline gap-3">
                <span className="truncate font-mono text-sm font-semibold">{r.name}</span>
                {r.duration !== null && <span className="text-xs text-zinc-500">{r.duration.toFixed(2)}s</span>}
                <span className="text-xs text-zinc-600">{new Date(r.modified * 1000).toLocaleTimeString()}</span>
              </div>
              <audio
                controls
                preload="none"
                src={`/api/renders/${encodeURIComponent(r.name)}/file?v=${r.modified}`}
                className="mt-auto h-9 w-full pt-2"
              />
            </li>
          ))}
        </ul>
      )}
      <h2 className="mt-8 text-lg font-semibold">Downloads</h2>
      <p className="mt-1 text-sm text-zinc-400">Freesound originals cached on this machine.</p>
      <input
        value={tag}
        onChange={(e) => setTag(e.target.value)}
        placeholder="Filter by tag…"
        className="mt-4 w-full max-w-xs rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
        data-testid="library-tag"
      />
      {sounds.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-500" data-testid="library-empty">
          No downloads yet. Cache sounds from the Sounds page.
        </p>
      ) : (
        <ul
          className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
          data-testid="library-list"
        >
          {sounds.map((s) => (
            <li key={s.id} className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-xs text-zinc-400">{s.id}</span>
                <span className="truncate text-sm font-semibold" title={s.name}>
                  {s.name}
                </span>
                {s.duration ? <span className="text-xs text-zinc-500">{Number(s.duration).toFixed(1)}s</span> : null}
              </div>
              {(s.user_tags || []).length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {(s.user_tags || []).map((t) => (
                    <span key={t} className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <audio controls preload="none" src={`/api/sounds/${s.id}/file`} className="mt-auto h-9 w-full pt-2" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
