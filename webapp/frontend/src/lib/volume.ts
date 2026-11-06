const KEY = "sfx.volume";
const MUTE_KEY = "sfx.muted";

type State = { volume: number; muted: boolean };

let state: State = {
  volume: Math.min(1, Math.max(0, Number(localStorage.getItem(KEY) ?? "0.5"))),
  muted: localStorage.getItem(MUTE_KEY) === "1",
};
const listeners = new Set<(s: State) => void>();

function applyTo(el: HTMLMediaElement) {
  if (el.volume !== state.volume) el.volume = state.volume;
  if (el.muted !== state.muted) el.muted = state.muted;
}

function applyAll() {
  for (const el of document.querySelectorAll("audio")) applyTo(el);
}

export function getVolume(): State {
  return state;
}

export function setVolume(next: Partial<State>) {
  state = { ...state, ...next };
  localStorage.setItem(KEY, String(state.volume));
  localStorage.setItem(MUTE_KEY, state.muted ? "1" : "0");
  applyAll();
  for (const l of listeners) l(state);
}

export function subscribeVolume(listener: (s: State) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// One level for the whole page: every player follows it, a change on any player moves it,
// and starting one sound stops the others so candidates can be compared one at a time.
export function installGlobalVolume() {
  document.addEventListener(
    "play",
    (e) => {
      const el = e.target as HTMLMediaElement;
      applyTo(el);
      for (const other of document.querySelectorAll("audio")) if (other !== el) other.pause();
    },
    true,
  );
  document.addEventListener(
    "volumechange",
    (e) => {
      const el = e.target as HTMLMediaElement;
      if (el.volume !== state.volume || el.muted !== state.muted) setVolume({ volume: el.volume, muted: el.muted });
    },
    true,
  );
  document.addEventListener("loadedmetadata", (e) => applyTo(e.target as HTMLMediaElement), true);
}
