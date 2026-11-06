import { useCallback, useEffect, useState } from "react";
import { type Sound, api } from "../lib/api";

export default function Downloads() {
  const [sounds, setSounds] = useState<Sound[]>([]);
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

  return (
    <section>
      <h2 className="mt-10 text-lg font-semibold">Downloads</h2>
      <p className="mt-1 text-sm text-zinc-400">Freesound originals cached on this machine.</p>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      <input
        value={tag}
        onChange={(e) => setTag(e.target.value)}
        placeholder="Filter by tag…"
        className="mt-4 w-full max-w-xs rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
        data-testid="downloads-tag"
      />
      {sounds.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-500" data-testid="downloads-empty">
          No downloads yet.
        </p>
      ) : (
        <ul
          className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
          data-testid="downloads-list"
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
    </section>
  );
}
