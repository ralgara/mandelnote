# Mandelnote

NL-driven generative music. You type; Claude shapes the sound in SuperCollider in real time.

## Prerequisites

- **SuperCollider** — installed locally (Mac)
- **BlackHole 2ch** — virtual audio device for routing SC output to browser (`brew install blackhole-2ch`)
- **uv** — Python package manager (`brew install uv`)
- **`ANTHROPIC_API_KEY`** — set in your environment

## Starting a session

**1. SuperCollider**

Open `music.scd` in the SuperCollider IDE. Select all (`Cmd+A`), then evaluate (`Cmd+Return`).

Wait for the SC post window to show:

```
── music engine ready — start chat.py ──
```

**2. Python chat**

```bash
uv run python chat.py
```

`uv` manages its own virtualenv — no manual activation needed. Dependencies are installed automatically on first run from `uv.lock`.

**3. Converse**

```
you: start something dark and slow
claude: ...
you: add some bells, sparse
you:           ← press Enter alone to let Claude initiate a change
```

`Ctrl+C` ends the session.

## What Claude can do

Claude responds in natural language and embeds control blocks that take effect immediately.

### `<music>` — adjust built-in instruments

Four instruments ship in `music.scd`: `sub_drone`, `bells`, `pad`, `pulse`. Claude targets them with a JSON block:

```
<music>
{"sub_drone": {"gate": 1, "amp": 0.6, "freq": 38}, "bells": {"gate": 0}}
</music>
```

### `<harmony>` — set tempo, key, and chord progression

Starts a TempoClock in SC and cycles through chords automatically. All sequencers reading `~harm` sync immediately.

```
<harmony>
{"bpm": 88, "swing": 0.12, "bars_per_chord": 2,
 "progression": [
   {"label": "C7", "root": 48, "tones": [48,52,55,58], "scale": [48,50,52,53,55,57,58,60]},
   {"label": "F7", "root": 53, "tones": [53,57,60,63], "scale": [53,55,57,58,60,62,63,65]}
 ]}
</harmony>
```

### `<synth>` — create a new instrument on the fly

Claude writes a SuperCollider SynthDef, sends it to SC via OSC, and registers it so future `<music>` blocks can control it.

## Audio routing (Mac)

SC plays to BlackHole. In **Audio MIDI Setup**: create a Multi-Output Device with BlackHole + your speakers so you hear the output while the browser can also capture it via `getUserMedia`.

## Files

| File | Purpose |
|------|---------|
| `music.scd` | SuperCollider engine — SynthDefs, OSC handlers, harmonic clock |
| `chat.py` | Python bridge — Claude API + OSC client + conversation loop |
| `pyproject.toml` / `uv.lock` | Python dependencies (anthropic, python-osc) |
