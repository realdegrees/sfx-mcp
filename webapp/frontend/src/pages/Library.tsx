import { useCallback, useEffect, useState } from "react";
import { type Render, type Sound, api } from "../lib/api";

export default function Library() {
  const [sounds, setSounds] = useState<Sound[]>([]);
  const [renders, setRenders] = useState<Render[]>([]);
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

  useEffect(() => {
    const load = () =>
      api
        .renders()
        .then((d) => setRenders(d.results))
        .catch((e: Error) => setError(e.message));
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold" data-testid="library-title">
        Library
      </h1>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      <h2 className="mt-6 text-lg font-semibold">Renders</h2>
      <p className="mt-1 text-sm text-zinc-400">Sounds the agent designed. Refreshes by itself.</p>
      {renders.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-500">No renders yet.</p>
      ) : (
        <ul className="mt-4 space-y-2" data-testid="render-list">
          {renders.map((r) => (
            <li key={r.name} className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-sm font-semibold">{r.name}</span>
                {r.duration !== null && <span className="text-xs text-zinc-500">{r.duration.toFixed(2)}s</span>}
                <span className="text-xs text-zinc-600">{new Date(r.modified * 1000).toLocaleTimeString()}</span>
              </div>
              <audio
                controls
                preload="none"
                src={`/api/renders/${encodeURIComponent(r.name)}/file?v=${r.modified}`}
                className="mt-2 w-full"
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
        <ul className="mt-4 space-y-2" data-testid="library-list">
          {sounds.map((s) => (
            <li key={s.id} className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-xs text-zinc-400">{s.id}</span>
                <span className="text-sm font-semibold">{s.name}</span>
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
              <audio controls preload="none" src={`/api/sounds/${s.id}/file`} className="mt-2 w-full" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
