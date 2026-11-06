import { CheckCheck, Send } from "lucide-react";
import { useState } from "react";
import { type Slot, type Submission, api } from "../lib/api";

function statusLine(sub: Submission): { text: string; tone: string } {
  const at = sub.submitted_at ? new Date(sub.submitted_at).toLocaleTimeString() : "";
  switch (sub.status) {
    case "waiting":
      return { text: `Sent at ${at}. Waiting for the agent to pick it up.`, tone: "text-sky-300" };
    case "working":
      return {
        text: sub.agent_message || `The agent is working on ${sub.modify?.length ?? 0} change requests.`,
        tone: "text-amber-300",
      };
    case "done":
      return { text: sub.agent_message || "The agent finished this round.", tone: "text-emerald-300" };
    default:
      return { text: "Not sent yet. Send the review when you are done to wake the agent.", tone: "text-zinc-500" };
  }
}

export default function ReviewBar({
  slots,
  submission,
  onChanged,
}: { slots: Slot[]; submission: Submission; onChanged: () => void }) {
  const [error, setError] = useState("");
  const counts = { picked: 0, rejected: 0, modify: 0, pending: 0 };
  for (const s of slots) for (const c of s.candidates) counts[c.review.status ?? "pending"] += 1;
  const busy = submission.status === "waiting" || submission.status === "working";
  const line = statusLine(submission);

  return (
    <div className="sticky top-0 z-10 -mx-6 mt-4 border-b border-zinc-800 bg-zinc-950/95 px-6 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span className="text-emerald-400">{counts.picked} picked</span>
        <span className="text-amber-400">{counts.modify} to modify</span>
        <span className="text-red-400">{counts.rejected} rejected</span>
        <span className="text-zinc-400">{counts.pending} undecided</span>
        <span className="ml-auto flex gap-2">
          <button
            type="button"
            disabled={counts.pending === 0}
            onClick={() =>
              api
                .pickRemaining()
                .then(onChanged)
                .catch((e: Error) => setError(e.message))
            }
            className="flex items-center gap-1 rounded bg-zinc-800 px-3 py-1.5 text-xs text-emerald-300 hover:bg-zinc-700 disabled:opacity-40"
          >
            <CheckCheck size={14} /> Pick all remaining
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              api
                .submit()
                .then(onChanged)
                .catch((e: Error) => setError(e.message))
            }
            className="flex items-center gap-1 rounded bg-sky-700 px-3 py-1.5 text-xs text-white hover:bg-sky-600 disabled:opacity-40"
          >
            <Send size={14} /> Send review to agent
          </button>
        </span>
      </div>
      <p className={`mt-1 text-xs ${line.tone}`}>{line.text}</p>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}
