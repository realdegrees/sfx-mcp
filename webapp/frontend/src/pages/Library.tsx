import { useCallback, useEffect, useState } from "react";
import ReviewBoard from "../components/ReviewBoard";
import { type Slot, api } from "../lib/api";

export default function Library() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .picked()
      .then((d) => {
        setSlots(d.slots);
        setLoaded(true);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  const count = slots.reduce((n, s) => n + s.candidates.length, 0);

  return (
    <div>
      <h1 className="text-xl font-bold" data-testid="library-title">
        Library
      </h1>
      <p className="mt-1 text-sm text-zinc-400">
        Sounds you picked, grouped by what they are for. Unpick one to send it back to Review.
      </p>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {loaded && count === 0 ? (
        <p className="mt-6 text-sm text-zinc-500" data-testid="library-empty">
          Nothing picked yet. Pick sounds on the Review page.
        </p>
      ) : (
        <ReviewBoard slots={slots} onSaved={load} compact />
      )}
    </div>
  );
}
