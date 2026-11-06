import { useCallback, useEffect, useState } from "react";
import ReviewBar from "../components/ReviewBar";
import ReviewBoard from "../components/ReviewBoard";
import { type Slot, type Submission, api } from "../lib/api";

export default function Review() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [round, setRound] = useState({ id: "", title: "" });
  const [submission, setSubmission] = useState<Submission>({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .board()
      .then((d) => {
        setSlots(d.slots);
        setRound({ id: d.id, title: d.title });
        setLoaded(true);
      })
      .catch((e: Error) => setError(e.message));
    api
      .submission()
      .then((d) => setSubmission(d.submission))
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  const current = submission.round === round.id ? submission : {};

  return (
    <div>
      <h1 className="text-xl font-bold" data-testid="review-title">
        Review{round.title && <span className="font-normal text-zinc-400">: {round.title}</span>}
      </h1>
      <p className="mt-1 max-w-4xl text-sm text-zinc-400">
        The agent's current request. Pick what to keep, reject what to drop, or ask for a change with the wrench and say
        what to change. Then send the review: the agent wakes up, works through the changes and puts the revised sounds
        back here. Picks also land in the Library.
      </p>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      {loaded && slots.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-500">No open request from the agent.</p>
      ) : (
        <>
          <ReviewBar slots={slots} submission={current} onChanged={load} />
          <ReviewBoard slots={slots} onSaved={load} />
        </>
      )}
    </div>
  );
}
