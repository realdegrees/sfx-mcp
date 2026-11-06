import { Volume2, VolumeX } from "lucide-react";
import { useEffect, useState } from "react";
import { getVolume, setVolume, subscribeVolume } from "../lib/volume";

export default function VolumeControl({ collapsed }: { collapsed: boolean }) {
  const [state, setState] = useState(getVolume());

  useEffect(() => subscribeVolume(setState), []);

  return (
    <div className="flex items-center gap-2 px-3 pb-3" data-testid="global-volume">
      <button
        type="button"
        onClick={() => setVolume({ muted: !state.muted })}
        className="rounded p-1 text-zinc-300 hover:bg-zinc-800"
        aria-label={state.muted ? "Unmute all sounds" : "Mute all sounds"}
        title={state.muted ? "Unmute all sounds" : "Mute all sounds"}
      >
        {state.muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
      </button>
      {!collapsed && (
        <>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(state.volume * 100)}
            onChange={(e) => setVolume({ volume: Number(e.target.value) / 100, muted: false })}
            className="w-full accent-zinc-300"
            aria-label="Volume for all sounds"
          />
          <span className="w-8 text-right font-mono text-xs text-zinc-400">{Math.round(state.volume * 100)}</span>
        </>
      )}
    </div>
  );
}
