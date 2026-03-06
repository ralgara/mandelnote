#!/usr/bin/env python3
"""
Generative music chat — natural language drives SuperCollider in real time.

Usage:
    uv run python chat.py

Prerequisites:
    1. Open music.scd in SuperCollider IDE, select all (Cmd+A), evaluate (Cmd+Return).
    2. Wait for "music engine ready" in SC post window.
    3. Run this script.
"""

import json
import re
import shutil
import textwrap
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from pythonosc import udp_client

# ── ANSI colors ───────────────────────────────────────────────────────────────

class C:
    R       = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    USER    = '\033[96m'    # bright cyan
    CLAUDE  = '\033[97m'    # bright white
    HARMONY = '\033[93m'    # bright yellow
    SYNTH   = '\033[35m'    # magenta
    CODE    = '\033[33m'    # amber — SC code
    ON      = '\033[92m'    # bright green
    OFF     = '\033[90m'    # dark gray
    PARAM   = '\033[94m'    # bright blue
    SEP     = '\033[90m'    # dark gray
    HINT    = '\033[90m'    # dim hints / paths
    ERR     = '\033[91m'    # bright red

# ── Terminal layout ───────────────────────────────────────────────────────────

W = shutil.get_terminal_size((100, 24)).columns

def _sep(char: str = '─', color: str = C.SEP) -> None:
    print(f"{color}{char * W}{C.R}")

def _print_user(text: str) -> None:
    print()
    _sep()
    if text:
        print(f" {C.USER}{C.BOLD}◉  you{C.R}  {text}")
    else:
        print(f" {C.USER}{C.BOLD}◉  you{C.R}  {C.DIM}(no input — Claude initiates){C.R}")
    print()

def _print_claude(text: str) -> None:
    print()
    _sep()
    print(f" {C.CLAUDE}{C.BOLD}◈  claude{C.R}")
    _sep()
    for para in text.split('\n'):
        if para.strip():
            wrapped = textwrap.fill(para, width=W - 2,
                                    initial_indent=' ', subsequent_indent=' ')
            print(f"{C.CLAUDE}{wrapped}{C.R}")
        else:
            print()
    print()

def _print_harmony(harmony: dict) -> None:
    prog  = ' → '.join(c['label'] for c in harmony.get('progression', []))
    bpm   = harmony.get('bpm', '?')
    swing = harmony.get('swing', 0)
    print(f"\n  {C.HARMONY}♩  harmony   {C.R}"
          f"{bpm} BPM · swing {swing}  "
          f"{C.HARMONY}[ {prog} ]{C.R}")

def _print_synth_block(synth: dict, saved_path: "Path | None") -> None:
    name  = synth['name']
    title = f" SC synth: {name} "
    bar_w = max(2, W - len(title) - 5)
    print()
    print(f"  {C.SYNTH}┌─{title}{'─' * bar_w}┐{C.R}")
    for raw_line in synth['code'].splitlines():
        max_inner = W - 7
        display = raw_line[:max_inner - 1] + '…' if len(raw_line) > max_inner else raw_line
        print(f"  {C.SYNTH}│{C.R}  {C.CODE}{display}{C.R}")
    print(f"  {C.SYNTH}└{'─' * (W - 4)}┘{C.R}")
    if saved_path:
        print(f"  {C.HINT}  ↳ saved {saved_path}{C.R}")
    print()

def _print_update(update: dict) -> None:
    for name, params in update.items():
        gate  = params.get('gate')
        other = {k: v for k, v in params.items() if k != 'gate'}
        parts = []
        if gate is not None:
            if int(gate) == 1:
                parts.append(f"{C.ON}ON{C.R}")
            else:
                parts.append(f"{C.OFF}OFF{C.R}")
        for k, v in other.items():
            v_str = str(round(v, 3)) if isinstance(v, float) else str(v)
            parts.append(f"{C.PARAM}{k}{C.R}={v_str}")
        print(f"  {C.DIM}◆{C.R}  {name:<16}{'  '.join(parts)}")

# ── Session logger ─────────────────────────────────────────────────────────────

class Logger:
    def __init__(self) -> None:
        Path("logs").mkdir(exist_ok=True)
        Path("synths").mkdir(exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = Path(f"logs/session_{ts}.log")
        self._f   = open(self.path, 'w', buffering=1)  # line-buffered
        self._write("session", f"started — {self.path}")

    def _write(self, kind: str, detail: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._f.write(f"[{ts}] {kind:<14} {detail}\n")

    def msg(self, role: str, text: str) -> None:
        self._write(role, text.replace('\n', ' ')[:300])

    def harmony(self, h: dict) -> None:
        prog = ' → '.join(c['label'] for c in h.get('progression', []))
        self._write("harmony", f"{h.get('bpm')} BPM  swing={h.get('swing', 0)}  [{prog}]")

    def gate(self, name: str, val: float) -> None:
        self._write("gate", f"{name} → {'ON' if int(val) == 1 else 'OFF'}")

    def set_(self, name: str, param: str, val: float) -> None:
        self._write("set", f"{name}.{param} = {round(val, 4)}")

    def synth(self, name: str, path: "Path | None") -> None:
        saved = f"  saved → {path}" if path else ""
        self._write("synth", f"created '{name}'{saved}")

    def save_synth(self, name: str, code: str) -> Path:
        ts   = datetime.now().strftime("%H%M%S")
        path = Path(f"synths/{name}_{ts}.scd")
        path.write_text(code)
        return path

    def close(self) -> None:
        self._write("session", "ended")
        self._f.close()

# ── OSC client ────────────────────────────────────────────────────────────────

osc = udp_client.SimpleUDPClient("127.0.0.1", 57120)

# ── Musical state ─────────────────────────────────────────────────────────────

DEFAULT_STATE: dict[str, dict] = {
    "sub_drone": {"gate": 0, "freq": 45.0,  "amp": 0.55, "detune": 0.4,  "lfoRate": 0.08, "sendAmt": 0.5 },
    "bells":     {"gate": 0, "density": 0.2, "brightness": 0.7, "amp": 0.4,  "sendAmt": 0.85},
    "pad":       {"gate": 0, "amp": 0.25, "filterFreq": 1200.0, "filterRQ": 0.4, "attack": 5.0, "sendAmt": 0.6 },
    "pulse":     {"gate": 0, "rate": 2.0,  "amp": 0.25, "filterFreq": 400.0, "sendAmt": 0.3 },
}

state: dict[str, dict] = {k: dict(v) for k, v in DEFAULT_STATE.items()}
harmony_state: dict = {"bpm": None, "swing": 0.0, "progression": []}

# ── Instrument catalog ────────────────────────────────────────────────────────

CATALOG = """
INSTRUMENTS
-----------
sub_drone — deep, powerful sub bass; thick stereo oscillator cluster with slow pitch drift
  gate: 0 (off) or 1 (on)
  freq: 30–80 Hz
  amp: 0.0–1.0
  detune: 0.0–2.0  (oscillator spread; higher = thicker, more beating)
  lfoRate: 0.01–0.5  (pitch drift speed; 0.05 = slow swell, 0.3 = wavering)
  sendAmt: 0.0–1.0  (reverb send)

bells — sparse, ethereal high-register metallic hits; Ringz resonators, random timing
  gate: 0 or 1
  density: 0.05–2.0  (hits per second; 0.1 = very sparse, 1.5 = busy shimmer)
  brightness: 0.1–1.0  (0.2 = low dark tones, 1.0 = high crystalline)
  amp: 0.0–0.8
  sendAmt: 0.0–1.0  (keep high for ethereal wash)

pad — mid-range filtered texture; 6 drifting VarSaw voices, very slow fade in/out
  gate: 0 or 1
  amp: 0.0–0.8
  filterFreq: 200–8000 Hz  (timbre; lower = darker/warmer)
  filterRQ: 0.1–2.0  (resonance; 0.1 = narrow peak, 1.5 = open)
  attack: 1–15  (fade-in seconds; use high values for slow swells)
  sendAmt: 0.0–1.0

pulse — soft rhythmic element; pitched click + pink noise layer
  gate: 0 or 1
  rate: 0.25–8.0  (beats per second; 0.5 = slow heartbeat, 4.0 = rapid)
  amp: 0.0–0.6
  filterFreq: 100–2000 Hz  (click pitch/color)
  sendAmt: 0.0–1.0
""".strip()

# ── Prompt sections ───────────────────────────────────────────────────────────

SYNTH_CONVENTIONS = """
CREATING NEW INSTRUMENTS
------------------------
You can synthesize anything that isn't already available by creating a new SuperCollider
SynthDef on the fly. Use a <synth> block — the code is sent to SC and evaluated immediately.

Strict conventions (required for routing to work):
- Use SINGLE-QUOTED symbols throughout: 'name' not \\name (avoids JSON escaping issues)
- Every SynthDef must include args: out=0, rev=0, gate=0, ..., sendAmt=X
- Use Linen.kr(gate, attackTime, 1, releaseTime, 0) to control amplitude envelope
- Write to BOTH outputs: Out.ar(out, sig) and Out.ar(rev, sig * sendAmt)
- Wrap in a Routine so the SynthDef registers on the server before instantiation
- CRITICAL: ALL var declarations must appear at the TOP of the SynthDef function body,
  before any other statements. SuperCollider forbids var declarations after expressions.
  Declare every variable you will use upfront, then assign them below.

Format:

<synth>
name: your_name
params: {"gate": 0, "amp": 0.4, "param1": 1.0, "sendAmt": 0.8}
---
Routine {
    SynthDef('your_name', {
        |out=0, rev=0, gate=0, amp=0.4, param1=1.0, sendAmt=0.8|
        var env, sig, other;  // declare ALL vars first — no var after any statement
        env = Linen.kr(gate, 2, 1, 3, 0);
        other = ...; // intermediate signals
        sig = Pan2.ar(other * amp * env, 0); // make it stereo
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;
    s.sync;
    ~synths['your_name'] = Synth('your_name', ['rev', ~rev]);
    "your_name ready".postln;
}.play;
</synth>

After creating a synth, use a <music> block to activate it (gate: 1).
Errors appear in the SC post window — if a synth doesn't respond, check there.

READING HARMONIC STATE IN SEQUENCERS
When a harmony is active, read ~harm in your sequencer code:
  ~harm[\\tones]  — Array of MIDI ints for current chord  (use .choose or index)
  ~harm[\\scale]  — Array of MIDI ints for current scale  (for melody voices)
  ~harm[\\root]   — Root MIDI note
  ~harm[\\label]  — Chord name string (e.g. "C7")
  ~swing          — Swing amount 0.0–0.5 (timing offset on off-beats)
Convert MIDI to Hz: midiNote.midicps
Example note choice: var note = ~harm[\\tones].choose.midicps;
""".strip()

HARMONY_DOCS = """
SETTING HARMONY
---------------
Use a <harmony> block to establish key, tempo, and chord progression.
SC receives it, starts a clock, and cycles through chords automatically.
All sequencers reading ~harm[\\tones] / ~harm[\\scale] sync to it immediately.

<harmony>
{{
  "bpm": 88,
  "swing": 0.12,
  "bars_per_chord": 2,
  "progression": [
    {{"label": "C7", "root": 48, "tones": [48,52,55,58], "scale": [48,50,52,53,55,57,58,60]}},
    {{"label": "F7", "root": 53, "tones": [53,57,60,63], "scale": [53,55,57,58,60,62,63,65]}},
    {{"label": "G7", "root": 55, "tones": [55,59,62,65], "scale": [55,57,59,60,62,64,65,67]}}
  ]
}}
</harmony>

Fields:
- tones: MIDI notes of the chord (for bass and chord voices)
- scale: available melody notes over this chord (chord tones + passing tones you choose)
- bars_per_chord: how many 4/4 bars each chord lasts (use 2 or 4 to start)
- swing: 0.0 = straight, 0.1–0.2 = light shuffle (read as ~swing in sequencers)
You can reissue <harmony> at any time to change key, tempo, or progression mid-session.
""".strip()

SYSTEM = f"""You are a musical co-creator in a live generative music session. \
The music is playing right now in SuperCollider. You and the user are shaping it together — \
either of you can drive changes or simply talk about what's happening.

{CATALOG}

When you want to change the music, embed a JSON block anywhere in your response:

<music>
{{
  "sub_drone": {{"gate": 1, "amp": 0.6, "freq": 38}},
  "bells": {{"gate": 1, "density": 0.12, "brightness": 0.85}}
}}
</music>

Rules for the music block:
- Only include instruments and parameters you want to change. Omitted ones stay as-is.
- gate 1 activates an instrument with a smooth fade-in; gate 0 silences it with a fade-out.
- Changes apply immediately and silently — you don't need to narrate the JSON.

{HARMONY_DOCS}

{SYNTH_CONVENTIONS}

How to engage:
- Respond naturally to what the user says, and change the music when it fits.
- You can initiate changes yourself ("I want to try something darker here...") and apply them.
- You can create new instruments whenever the existing palette isn't enough.
- You can appreciate what's working, suggest ideas without applying them, or ask questions.
- Think musically: dynamics, space, contrast, texture, tension, release.
- Keep responses concise — you're a collaborator in an ongoing session, not an explainer.

The current musical state is prepended to each user message so you always know what's active."""

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_state() -> str:
    lines = []
    if harmony_state.get("bpm"):
        prog = " → ".join(c["label"] for c in harmony_state["progression"])
        lines.append(f"Harmony: {harmony_state['bpm']} BPM  swing={harmony_state['swing']}  [{prog}]")
    lines.append("Instruments:")
    for name, params in state.items():
        status = "ON " if params.get("gate", 0) == 1 else "off"
        detail = "  ".join(
            f"{k}={round(v, 3) if isinstance(v, float) else v}"
            for k, v in params.items()
            if k != "gate"
        )
        lines.append(f"  {name}: [{status}]  {detail}")
    return "\n".join(lines)


def extract_harmony(text: str) -> "tuple[dict | None, str]":
    match = re.search(r"<harmony>\s*(.*?)\s*</harmony>", text, re.DOTALL)
    if not match:
        return None, text
    try:
        harmony = json.loads(match.group(1))
        clean = re.sub(r"\s*<harmony>.*?</harmony>\s*", "\n", text, flags=re.DOTALL).strip()
        return harmony, clean
    except json.JSONDecodeError:
        return None, text


def extract_music(text: str) -> "tuple[dict | None, str]":
    match = re.search(r"<music>\s*(.*?)\s*</music>", text, re.DOTALL)
    if not match:
        return None, text
    try:
        update = json.loads(match.group(1))
        clean = re.sub(r"\s*<music>.*?</music>\s*", "\n", text, flags=re.DOTALL).strip()
        return update, clean
    except json.JSONDecodeError:
        return None, text


def extract_synth(text: str) -> "tuple[dict | None, str]":
    match = re.search(r"<synth>\s*(.*?)\s*</synth>", text, re.DOTALL)
    if not match:
        return None, text
    content = match.group(1)
    parts = content.split("---", 1)
    if len(parts) != 2:
        return None, text
    meta_lines, code = parts
    meta: dict = {}
    for line in meta_lines.strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    name = meta.get("name", "").strip()
    try:
        params = json.loads(meta.get("params", "{}"))
    except json.JSONDecodeError:
        params = {}
    if not name:
        return None, text
    clean = re.sub(r"\s*<synth>.*?</synth>\s*", "\n", text, flags=re.DOTALL).strip()
    return {"name": name, "params": params, "code": code.strip()}, clean

# ── Apply actions ─────────────────────────────────────────────────────────────

def apply_harmony(harmony: dict, log: Logger) -> None:
    _print_harmony(harmony)
    osc.send_message("/music/harmony", [json.dumps(harmony)])
    log.harmony(harmony)
    harmony_state["bpm"]         = harmony.get("bpm")
    harmony_state["swing"]       = harmony.get("swing", 0.0)
    harmony_state["progression"] = harmony.get("progression", [])


def apply_synth(synth: dict, log: Logger) -> None:
    saved = log.save_synth(synth["name"], synth["code"])
    _print_synth_block(synth, saved)
    osc.send_message("/sc/eval", [synth["code"]])
    log.synth(synth["name"], saved)
    state[synth["name"]] = {"gate": 0, **synth["params"]}


def apply_update(update: dict, log: Logger) -> None:
    _print_update(update)
    for instrument, params in update.items():
        if instrument not in state:
            continue
        if "gate" in params:
            val = float(params["gate"])
            osc.send_message("/music/gate", [instrument, val])
            log.gate(instrument, val)
            state[instrument]["gate"] = int(val)
        for param, value in params.items():
            if param == "gate":
                continue
            osc.send_message("/music/set", [instrument, param, float(value)])
            log.set_(instrument, param, float(value))
            state[instrument][param] = value

# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    log    = Logger()
    client = Anthropic()
    messages: list[dict] = []

    _sep('═')
    print(f" {C.BOLD}Mandelnote{C.R}  generative music session")
    print(f" {C.HINT}SuperCollider should show 'music engine ready' in the post window")
    print(f" {C.HINT}log → {log.path}{C.R}")
    _sep('═')
    print(f"\n {C.DIM}Type to talk. Press Enter alone to let Claude initiate. Ctrl+C to quit.{C.R}\n")

    try:
        while True:
            try:
                user_input = input(f" {C.USER}◉{C.R}  you  ›  ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            _print_user(user_input)
            log.msg("user", user_input or "(no input)")

            state_header = format_state()
            if user_input:
                content = f"{state_header}\n\n{user_input}"
            else:
                content = f"{state_header}\n\n[No input — feel free to initiate a change or reflect on the music.]"

            messages.append({"role": "user", "content": content})

            print(f"  {C.DIM}⟳  thinking…{C.R}", end='', flush=True)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=SYSTEM,
                messages=messages,
            )
            print(f"\r{' ' * 20}\r", end='', flush=True)

            reply = response.content[0].text
            log.msg("claude", reply)

            # Process in order: harmony → synth → music
            harmony, reply = extract_harmony(reply)
            if harmony:
                try:
                    apply_harmony(harmony, log)
                except Exception as e:
                    print(f"  {C.ERR}⚠  harmony error: {e}{C.R}")

            synth, reply = extract_synth(reply)
            if synth:
                try:
                    apply_synth(synth, log)
                except Exception as e:
                    print(f"  {C.ERR}⚠  synth error: {e}{C.R}")

            update, reply = extract_music(reply)
            if update:
                try:
                    apply_update(update, log)
                except Exception as e:
                    print(f"  {C.ERR}⚠  osc error: {e}{C.R}")

            _print_claude(reply)

            messages.append({"role": "assistant", "content": reply})
            if len(messages) > 30:
                messages = messages[-30:]

    finally:
        print(f"\n{C.DIM}Session ended.{C.R}")
        log.close()


if __name__ == "__main__":
    main()
