# Game SFX design guide

Rules of thumb collected from sound designers' writing (sources at the end), mapped onto this
server's effect types. Every number is a starting point, not an answer: a descriptive word has
no single correct translation, the source material decides how far a move can go, and only a
listener can judge the result. The measurements from `audio_inspect` tell you what changed,
never whether it sounds good.

## Workflow
Keywords: workflow, how, start, process, approach, candidates, iterate, listen

1. Inspect the source (`audio_inspect`): duration, peak, loudness, crest (punch), spectral
   centroid (brightness), silence at the edges.
2. Plan: turn each word of the request into moves with the tables below. When a word is
   ambiguous ("magical", "bigger"), render two or three candidates that read it differently
   rather than guessing one, and name them so the listener can tell them apart
   (`orb_pitchdown`, `orb_shimmer`).
3. Render, then inspect the result with `compare_with` set to the source and check the numbers
   moved the way you meant (deeper means the centroid went down, punchier means crest went up).
4. Hand the candidates to the listener (they play in the web UI's Library under Renders) and
   revise from what they say, changing one or two things at a time.
5. Keep projects: a revision is an edit of the saved project (`audio_project` get, change,
   `audio_render`), never a rebuild.

## Frequency map
Keywords: frequency, eq, hz, band, spectrum, range, where

The charts disagree by an octave or so at every edge; these are the overlapping consensus
ranges.

| Range | Word for too little | Word for too much |
|---|---|---|
| 20 to 60 Hz sub | weak, small, no weight | rumble, boomy, eats headroom |
| 60 to 250 Hz bass | thin, light | boomy, heavy, bloated |
| 200 to 500 Hz low mids | hollow, cold | muddy, boxy (300 to 500), cardboard |
| 500 Hz to 2 kHz mids | distant, scooped | honky, nasal, telephone |
| 2 to 5 kHz upper mids | dull, far away | harsh, piercing, presence fatigue |
| 5 to 10 kHz highs | dull, soft, muffled | sizzle, sibilant, crunchy |
| 10 kHz and up air | closed, dark | hissy, brittle |

Cut narrow (`eq` q 4 to 10) to remove a problem; boost wide (q 0.5 to 1.5) to add character.
Cutting what is in the way usually works better than boosting what is missing.

## Deeper, heavier, bigger, more weight
Keywords: deeper, deep, heavier, heavy, bigger, big, huge, massive, larger, weight, powerful, epic, giant, low, boom

- Pitch down tape-style: `pitch` -3 to -12 semitones with `preserve_duration: false`. Lower and
  slower reads as larger and heavier; it is the single strongest size cue. Pitching down dulls
  the top end, so layer the original (or a click) back on top for definition.
- Add a sub layer: a separate low layer (pitched-down copy, a low thump or boom) with
  `lowpass` 120 to 200 Hz. Only one layer should own the sub; `highpass` the others at 80 to
  150 Hz so the lows do not pile up into mud.
- `low_shelf` +3 to +6 dB at 80 to 120 Hz on the body layer.
- Light `saturate` (drive 3 to 9 dB) on the low layer: harmonics make bass audible on small
  speakers and read as power.
- Longer tail: `reverb` decay 1.5 to 3 s at low wet (0.15 to 0.3), or a longer fade-out.
- Bigger is also wider: `stereo_width` 1.2 to 1.5 on the body and tail, never on the sub.

## Smaller, lighter, thinner, cuter
Keywords: smaller, small, lighter, light, thinner, thin, tiny, cute, toy, weak, little, high

- Pitch up tape-style: `pitch` +2 to +7 semitones, `preserve_duration: false`.
- `highpass` 150 to 400 Hz; drop the sub layer entirely.
- Shorter tail: `fade` out sooner, less or no reverb.

## Brighter, crisper, clearer, more presence
Keywords: brighter, bright, crisp, crisper, clearer, clear, presence, sharper, detail, sparkle, shiny, airy, air, open, closer

- `high_shelf` +2 to +6 dB at 5 to 8 kHz (crisp) or 10 to 12 kHz (air).
- `eq` +2 to +4 dB, q 1, at 2 to 4 kHz for presence; go easy, it turns harsh fast.
- Cut the mud that masks the top: `eq` -2 to -4 dB at 250 to 400 Hz.
- Check: spectral centroid goes up.

## Darker, warmer, softer, duller
Keywords: darker, dark, warmer, warm, softer, soft, duller, dull, mellow, smooth, round, gentle, muffled

- `high_shelf` -3 to -8 dB at 4 to 6 kHz, or `lowpass` 3 to 8 kHz for clearly darker.
- `low_shelf` +2 to +3 dB at 150 to 250 Hz for warmth.
- Behind a wall, underwater, inside: `lowpass` 400 to 1200 Hz with slope 24, plus reverb for a
  room; underwater adds slow `vibrato` (rate 0.5 to 1.5 Hz, depth 0.1 to 0.2).
- Check: spectral centroid goes down.

## Less harsh, less piercing
Keywords: harsh, piercing, shrill, painful, fatiguing, sharp, tinny, screechy, abrasive, ear

- Find the resonance and cut it: `eq` -3 to -8 dB, q 3 to 6, somewhere in 2 to 5 kHz (try
  3 kHz first, then 2.5 or 4). Sizzle lives higher: 6 to 10 kHz.
- A gentle `high_shelf` -2 to -4 dB at 6 kHz as a broad alternative.
- Saturation and limiting add harshness; back them off before EQing.

## Muddy, boomy, boxy
Keywords: muddy, mud, boomy, boxy, cardboard, cloudy, unclear, congested, woolly

- Muddy: `eq` -3 to -6 dB, q 1 to 2, at 200 to 350 Hz.
- Boxy: `eq` -3 to -6 dB, q 2 to 4, at 300 to 500 Hz.
- Boomy: `highpass` 40 to 80 Hz plus `eq` -3 dB around 100 to 150 Hz.
- In a layered sound, mud is usually several layers sharing the same lows: highpass all but
  one.

## Punchier, sharper attack, snappier (keep the tail)
Keywords: punchier, punch, punchy, attack, snappier, snappy, transient, tighter, tight, impact, hit, sharper, crack, click

- Add a transient layer: a short click, crack or snap (trim to 10 to 50 ms, `fade` out 5 to
  20 ms) at offset 0, `highpass` 1 to 3 kHz so it only adds the front edge.
- `compressor` with slow attack (20 to 50 ms), ratio 3 to 6, release 80 to 200 ms: the hit
  passes before the compressor clamps, so the attack stands out from the body. A fast attack
  does the opposite.
- `trim_silence` at the start: any silence before the hit reads as lag in a game.
- Check: crest_db goes up.

## Softer attack, gentler
Keywords: softer attack, gentle, smooth onset, swell, fade in, less clicky, rounder

- `fade` in 10 to 80 ms; `compressor` with fast attack (0.5 to 3 ms); `high_shelf` cut.
- Check: crest_db goes down.

## Longer or shorter
Keywords: longer, shorter, length, duration, stretch, extend, faster, slower, quick, fit, time

- Change length without changing pitch: `speed` with `preserve_pitch: true`, factor =
  current duration / target duration. Stays natural within about 0.75 to 1.33; beyond that it
  smears transients.
- Shorter tail only: `fade` out earlier with an exponential curve, or `gate`.
- Longer tail: `reverb`, `echo`, or a separate tail layer.
- Slower and lower together is the tape move (`pitch` with `preserve_duration: false`).

## More space, distant, far away
Keywords: distant, distance, far, faraway, away, space, roomy, room, hall, cave, echo, reverb, ambient, outside, background

Perceived distance is mostly level, then the ratio of reverb to direct sound, then lost highs.
Use all three together:
- `gain` -6 to -18 dB.
- `reverb` with higher wet (0.4 to 0.7); small room decay 0.3 to 0.8 s, hall 1.5 to 3 s, cave or
  cathedral 3 to 8 s; `predelay_ms` 10 to 40 for a big space.
- `lowpass` 4 to 8 kHz, or a `high_shelf` cut.
- Softer transients (compressor fast attack, or fade in a few ms).
- In a game, prefer leaving distance and room to the engine for 3D sounds (see Game delivery).

## Closer, drier, more intimate
Keywords: closer, close, drier, dry, intimate, upfront, in your face, present

- Less or no reverb, shorter tail, slight `low_shelf` boost (proximity), presence at 2 to 4 kHz,
  more crest (transients).

## Metallic, ringing, resonant
Keywords: metallic, metal, ringing, ring, resonant, clang, steel, iron, bell, tonal, sword, anvil

- Resonant peaks: one or two narrow `eq` boosts (+6 to +12 dB, q 8 to 20) at inharmonic
  frequencies, for example 1.2 kHz and 3.3 kHz.
- `flanger` with high regen (60 to 90), little depth (0.5 to 2 ms): a comb filter rings
  metallically.
- A short bright `reverb` (decay 0.3 to 0.8 s, damping 12 to 16 kHz) for ring-out.
- Best: layer a real metal hit (search the library) under the original.

## Magical, ethereal, shimmering, mystical
Keywords: magical, magic, ethereal, shimmer, shimmering, sparkly, sparkle, mystical, fantasy, spell, enchanted, fairy, arcane, otherworldly, dreamy, celestial

"Magical" has several real readings; render more than one:
- Shimmer: `chorus` (mix 0.5 to 0.8) plus a long bright `reverb` (2 to 4 s, damping 12 kHz, wet
  0.4); optionally a copy pitched +12 semitones (`preserve_duration: true`) mixed 10 to 15 dB
  under.
- Swell: a reversed copy of the sound (`reverse`, then `reverb`, then `reverse` again) placed
  so it ends where the dry sound starts: the sound sucks in before it plays.
- Sparkle: high, tonal layers (chimes, bells, glass) `highpass` 2 kHz, stereo wide.
- Otherworldly: `vibrato` slow and shallow (rate 0.3 to 2 Hz, depth 0.1 to 0.3), `phaser`.
- Spell timing: a cast has a build and a release; the release (whoosh, crack) belongs on the
  frame the spell leaves the hand, not before.

## Ominous, menacing, dark, horror
Keywords: ominous, menacing, dark, horror, scary, creepy, sinister, evil, threatening, dread, foreboding, ghostly, ghost, eerie

- Low rumble layer: noise or a rumble pitched -12 or more, `lowpass` 150 Hz, slow `tremolo`
  (0.2 to 1 Hz, depth 0.3) so it breathes.
- Pitch the main sound down 3 to 7 semitones; long dark reverb (decay 3 to 6 s, damping 3 kHz).
- Ghostly: `reverse` swells, slow `vibrato`, heavy `lowpass` with `reverb` wet 0.6+.
- Dissonance: two copies a minor second or tritone apart (+1 or +6 semitones).

## Wobble, unstable, warble
Keywords: wobble, wobbly, warble, unstable, wavering, oscillating, pulsing, throb, vibrato, tremolo, modulate, wah

- Pitch wobble: `vibrato` (slow 1 to 4 Hz for a wobble, 5 to 8 Hz for a musical vibrato; depth
  0.2 to 0.8).
- Volume pulse: `tremolo`; above 15 Hz it turns into a buzz or flutter.
- Sweeping tone: `flanger` (jet) or `phaser` (swirl).

## Aggressive, gritty, dirty, distorted
Keywords: aggressive, gritty, grit, dirty, distorted, distortion, crunchy, crunch, angry, raw, overdriven, harsh tone, brutal, rough

- `saturate` drive 12 to 24 dB (hard style for crunch); follow with `limiter`.
- Raise 1 to 3 kHz slightly, add a slightly longer, rougher tail.
- Heavy weapons: push the body and sub layers, add saturation.

## Electric, sci-fi, energy
Keywords: electric, electricity, zap, spark, sci-fi, scifi, laser, energy, plasma, robotic, robot, synthetic, digital, futuristic, hum, buzz

- Fast `tremolo` (40 to 120 Hz) on a tone or noise layer: buzz and arcing.
- `flanger` with high regen; `bandpass` narrow sweeps; `pitch` ramps through layered copies.
- Lasers: short tonal layers pitched apart, with a fast downward pitch feel built from stacked
  copies at decreasing pitch and offsets of 10 to 20 ms.

## Wider, narrower
Keywords: wider, wide, width, stereo, narrower, narrow, mono, spread, enveloping

- `stereo_width` 1.2 to 1.8 wider, below 1 narrower; `chorus` widens too.
- Keep low frequencies (sub layers) narrow. 3D-positioned game sounds should be mono.

## Layering
Keywords: layer, layering, layers, combine, stack, overlap, mix, blend, compose, composite, build, together

A designed sound effect is usually three to five layers, each with one job:
- Transient (attack): a short click, crack or snap that gives definition. 10 to 50 ms.
- Body: the core character (the material, the creature, the weapon).
- Sub (weight): the low end. Only one layer owns it.
- Tail (release): debris, ring-out, reverb, a whoosh away.
- Sweetener: something unexpected and quiet that gives identity (an animal growl inside an
  engine, ice cracks inside a magic hit).

Rules:
- Each layer earns its place with a band of its own: `highpass` / `lowpass` layers so they do
  not fight. Mud and weakness both come from two layers fighting for the same band.
- Timing changes size and punch: layers within 0 to 30 ms fuse into one event; 40 ms and more
  reads as separate events (a flam). Delaying the body 5 to 20 ms after the transient makes the
  hit read larger.
- Level hierarchy: body loudest, transient and sub supporting, sweeteners 10 to 20 dB under.
- Pitching layers apart (a body at -5 semitones, a transient at +3) helps them separate.
- Render the composite and check the peak: summed layers clip easily; the project's
  `normalize_peak_db` fixes the final level, a master `limiter` tames the peaks.

## Impact, hit, punch
Keywords: impact, hit, punch, smash, slam, thud, strike, collision, crash, body hit, melee

Recipe: transient (crack, snap, or a short metal or wood hit) at 0 ms, body (thud, punch) at
0 to 15 ms, sub (pitched-down body, lowpass 150 Hz) at 0 to 20 ms, tail (debris, crumble,
short reverb) at 50 to 150 ms. Master: `compressor` slow attack, `limiter` -1 dB. Trim
leading silence to zero.

## Explosion
Keywords: explosion, explode, blast, boom, detonation, grenade, bomb, burst, fireball

Recipe: a sharp crack transient, a body (the explosion recording, pitched -2 to -6 tape style),
a big sub (pitched -12, lowpass 120 Hz, saturate 6 dB), and a long tail (debris and rumble,
`reverb` 2 to 4 s). Distant explosions lose the crack and highs and gain reverb (see Distance).

## Whoosh, swing, swipe
Keywords: whoosh, swoosh, swing, swipe, swish, slash, pass by, fly by, woosh, wind

- Shape: fade in, peak, fade out; the peak sits on the moment of fastest motion (the contact
  frame of a swing).
- Faster object = shorter and higher (`speed` 1.3 to 2, or pitch up); heavier object = longer
  and lower.
- A `flanger` or `phaser` sweep adds motion; `stereo_width` adds pass-by; a sweeping `bandpass`
  feel comes from layering two filtered copies.
- Cut its low end (`highpass` 100 to 200 Hz) so it does not mask the impact that follows.

## Magic cast and magic impact
Keywords: cast, casting, spell, charge, charging, buildup, release, projectile, fireball, heal, buff, shield, summon, teleport

- Charge or build: rising energy. Layer a reverse swell, a tone pitched up in steps across
  layers, increasing `tremolo` rate.
- Release: a whoosh plus a bright transient on the release frame.
- Impact: an impact recipe with a magical sweetener (shimmer, chimes, a pitched-up crackle).
- Healing and buffs read best bright, soft-attacked and rising; curses and debuffs dark,
  falling and dissonant.
- Deliver cast and impact as separate files so the game can time them independently.

## UI and interface
Keywords: ui, interface, menu, button, click, hover, notification, select, confirm, cancel, error, alert, ping, pop

- Short: most UI cues stay under 300 ms; hover cues 20 to 40 ms and very soft.
- Sit in the mid-high range (about 1 to 6 kHz); `highpass` 200 to 400 Hz so they never muddy
  the game mix. Hover sounds can live around 3 to 6 kHz.
- One tonal family per game: shared source material and tuning, so cues feel related.
- Positive and confirm cues move up in pitch, negative and cancel cues move down; errors are
  lower, duller or dissonant.
- Give each kind of action its own frequency slot so simultaneous cues do not mask.
- Sound must never be the only carrier of important information.

## Footsteps and foley
Keywords: footstep, footsteps, step, steps, foley, walk, run, cloth, movement, jump, land, surface

- Build a pool, not one sound: 4 to 8 variations per surface (`audio_variations`), played
  without immediate repeats.
- Variation: pitch +-1 to 2 semitones (keep it within about 10 percent, wider sounds like a
  different creature), level +-1.5 dB.
- Deliver dry and tight: trim the start to the heel strike, short exponential fade-out, no
  reverb (the engine adds the space).
- Heavier characters: pitch down 1 to 3 semitones, `low_shelf` +3 dB at 100 Hz.

## Creatures and animals
Keywords: creature, animal, monster, bird, gull, seagull, insect, beast, growl, roar, call, chirp, vocal, voice, critter, whale, crab

- Size follows pitch: tape-style pitch down for a bigger animal (formants drop with the pitch,
  which is what sells the size); pitch up for small.
- Monsters are layered animals: combine two or three (a lion roar body, a pig squeal transient,
  a walrus tail), pitched to blend.
- Keep calls dry and mono for 3D emitters; trim breaths and room noise with `trim_silence` and
  `gate`.
- Make several variations of each call (pitch +-1 to 3 semitones) so a flock does not repeat.

## Ambience beds and loops
Keywords: ambience, ambient, ambiance, bed, loop, loops, looping, background, atmosphere, atmos, room tone, wind, sea, ocean, surf, forest, rain, river, birds, crickets, night, day, seamless

- Structure a soundscape in tiers: a constant bed (wind, surf, room tone), an intermittent
  detail layer, and rare one-shots (a gull call, a branch crack) scattered by the game over
  time.
- Beds must not contain distinctive events: a memorable sound in a loop reveals the loop.
  Cut such events out (`trim`, or pick a cleaner region) and reuse them as one-shots.
- Seamless loop: `make_loop` as the last effect, crossfade 1 to 3 s for noisy beds (equal-power,
  so the level does not dip), shorter for tonal material. Pick a source region without strong
  transients near the ends.
- Length: 30 s to 2 min per bed; longer hides repetition, two beds of different lengths
  layered in the game hide it further.
- Level: beds sit well under gameplay sounds; normalize consistently and let the game set the
  mix.
- Day and night variants can come from one bed: darker EQ and less detail at night.

## Game delivery
Keywords: game, delivery, export, deliver, engine, unity, unreal, wwise, fmod, 3d, spatial, mono, format, loudness, normalize, final, variations, variation, repetition

- 3D-positioned sounds (a footstep, a creature, a gun) go out mono and dry; the engine pans,
  attenuates and adds the room. 2D sounds (UI, music stings, beds) can be stereo.
- Keep the dry sound separate from its environmental tail so each level can supply its own
  reverb.
- No silence before the onset (it reads as input lag); short fades at both ends to avoid
  clicks.
- Peak-normalize to -1 dBFS and keep a consistent loudness per category; set the real mix in
  the game.
- Repetition is the enemy: 3 to 5 or more variations per frequently played sound, plus small
  runtime pitch and level randomization in the engine.
- WAV, 48 kHz, 16 or 24-bit; let the engine compress.

## Variations
Keywords: variation, variations, variants, alternatives, versions, randomize, random, different, candidates, options

- `audio_variations` renders a project several times with seeded random pitch, level, timing
  and tone per layer. Seeds make it repeatable.
- Footsteps and impacts: pitch 1 to 2 semitones, gain 1.5 dB, timing 5 to 15 ms.
- Creature calls: pitch 2 to 3 semitones, timing small.
- UI: little or no variation; consistency matters more.
- For exploring a direction instead (more candidates for one request), render separate
  projects that differ in one deliberate choice each.

## Sources
Keywords: sources, references, citations, reading

- Weapon layering (transient, body, sub, mechanical, tail): https://violetrecording.com/how-to-design-weapon-sounds/
  and https://www.liortega.com/post/first-person-shooter-gun-sound-design
- Layer roles, one layer owns the sub: https://morphic.com/resources/how-to/how-to-layer-sound-effects
- Pitching down reads larger, add highs back: https://freesound.org/forum/production-techniques-music-gear-tips-and-tricks/37791
- Rising pitch as growth: https://boombox-post.squarespace.com/blog/2022/7/29/designing-a-super-sized-transformation
- Saturation for weight: https://www.production-expert.com/production-expert-1/adding-weight-and-impact-to-sound-design-with-boom-library-uberbass
- EQ trouble frequencies: https://www.prosoundweb.com/in-the-studio-the-6-trouble-frequencies/ and
  https://mastering.com/wp-content/uploads/2017/07/EQ-CHEAT-SHEET.pdf
- Variation ranges and pools: https://sfxengine.com/blog/common-game-audio-mistakes,
  https://bugnet.io/blog/how-to-implement-footstep-variation-to-avoid-repetition,
  https://uhiyama-lab.com/en/notes/ue/sound-cue-vs-sound-wave-best-practices/
- Magic spell timing and layering: https://www.gamedeveloper.com/audio/making-of-rpg-magic-2-sound-pack
- UI sounds: https://sfxengine.com/blog/best-practices-for-game-ui-sounds and
  https://violetrecording.com/how-to-design-ui-sounds/
- Loops and ambience tiers: https://gamedevbeginner.com/create-looping-sound-effects-for-games-for-free-with-audacity/,
  https://splice.com/blog/audio-soundscape-for-video-games,
  https://creatorsoundspro.com/looping-audio-seamlessly-a-practical-guide-for-game-developers-video-editors
- Distance cues (level, direct-to-reverb ratio, high loss): https://www.frontiersin.org/articles/10.3389/fpsyg.2017.00969/pdf
