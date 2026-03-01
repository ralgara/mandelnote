// ── Generative Music Engine ──────────────────────────────────────────────────
// Select all and evaluate (Cmd+A, then Cmd+Return).
// Python chat.py connects to localhost:57120 and drives instruments via OSC.
// SC posts "[gate]" and "[set]" lines as changes arrive — useful for debugging.

s.options.memSize = 65536;

(
s.waitForBoot {

    // ── SynthDefs ─────────────────────────────────────────────────────────────

    // Shared reverb — reads from ~rev bus; add LAST so it runs after sources.
    SynthDef(\reverb, {
        |in=0, out=0, room=0.88, damp=0.4|
        var sig = In.ar(in, 2);
        sig = FreeVerb2.ar(sig[0], sig[1], 1.0, room, damp);
        Out.ar(out, sig * 0.4);
    }).add;

    // Deep sub drone — sine/saw cluster, slow pitch drift.
    SynthDef(\sub_drone, {
        |out=0, rev=0, gate=0, freq=45, amp=0.55, detune=0.4, lfoRate=0.08, sendAmt=0.5|
        var env  = Linen.kr(gate, 4, 1, 5, 0);
        var lfo  = SinOsc.kr(lfoRate) * 2.5;
        var sigL = SinOsc.ar(freq + lfo)
                 + (SinOsc.ar(freq * 2 + lfo * 0.7) * 0.3)
                 + (VarSaw.ar(freq + detune + lfo, 0, 0.15) * 0.2);
        var sigR = SinOsc.ar(freq + lfo + 0.5)
                 + (SinOsc.ar(freq * 2 + lfo * 0.65 + 0.3) * 0.3)
                 + (VarSaw.ar(freq - detune + lfo, 0, 0.15) * 0.2);
        var sig  = LPF.ar([sigL, sigR], freq * 5) * amp * env;
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;

    // Ethereal bells — sparse metallic Ringz voices, per-trigger random pitch.
    SynthDef(\bells, {
        |out=0, rev=0, gate=0, density=0.2, brightness=0.7, amp=0.4, sendAmt=0.85|
        var env      = Linen.kr(gate, 2, 1, 3, 0);
        var baseFreq = brightness.linexp(0, 1, 500, 8000);
        var sig = Mix.fill(4, {|i|
            var trig = Dust.kr(density * (0.6 + i * 0.15));
            var freq = TExpRand.kr(baseFreq * 0.5, baseFreq * 2.5, trig);
            var decT = TRand.kr(1.5, 4.5, trig);
            Ringz.ar(K2A.ar(trig) * 0.008, freq, decT) * (1 / (i + 1))
        });
        sig = Pan2.ar(sig, LFNoise1.kr(0.15));
        sig = sig * amp * env;
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;

    // Pad — evolving filtered texture, slow attack, 6 drifting voices.
    SynthDef(\pad, {
        |out=0, rev=0, gate=0, amp=0.25, filterFreq=1200, filterRQ=0.4, attack=5.0, sendAmt=0.6|
        var env = Linen.kr(gate, attack, 1, 8, 0);
        var sig = Mix.fill(6, {|i|
            var freq  = ExpRand(150, 1200);
            var drift = LFNoise1.kr(ExpRand(0.02, 0.07)).range(0.99, 1.01);
            VarSaw.ar(freq * drift, 0, LFNoise1.kr(0.1).range(0.2, 0.8))
        });
        sig = RLPF.ar(sig * 0.15, filterFreq, filterRQ);
        sig = Pan2.ar(sig, LFNoise1.kr(0.07));
        sig = sig * amp * env;
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;

    // Pulse — soft rhythmic clicks, pitched + noise layer.
    SynthDef(\pulse, {
        |out=0, rev=0, gate=0, rate=2.0, amp=0.25, filterFreq=400.0, sendAmt=0.3|
        var env  = Linen.kr(gate, 1, 1, 2, 0);
        var trig = Impulse.kr(rate);
        var sig  = (SinOsc.ar(filterFreq) * EnvGen.kr(Env.perc(0.005, 0.25), trig))
                 + (PinkNoise.ar * EnvGen.kr(Env.perc(0.001, 0.08), trig) * 0.25);
        sig = RLPF.ar(sig, filterFreq * 2, 0.5);
        sig = Pan2.ar(sig, LFNoise0.kr(rate));
        sig = sig * amp * env;
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;

    s.sync;

    // ── Infrastructure ────────────────────────────────────────────────────────

    ~rev = Bus.audio(s, 2);

    // Source synths first — reverb reads from bus, so it must run after them.
    ~synths = Dictionary.new;
    ~synths[\sub_drone] = Synth(\sub_drone, [\rev, ~rev]);
    ~synths[\bells]     = Synth(\bells,     [\rev, ~rev]);
    ~synths[\pad]       = Synth(\pad,       [\rev, ~rev]);
    ~synths[\pulse]     = Synth(\pulse,     [\rev, ~rev]);
    Synth(\reverb, [\in, ~rev]); // last

    // ── OSC Handlers ──────────────────────────────────────────────────────────

    // /music/gate  instrumentName  value(0|1)
    OSCdef(\gate, { |msg|
        var name = msg[1].asSymbol;
        var val  = msg[2].asFloat;
        ~synths[name] !? { |syn| syn.set(\gate, val) };
        "[gate] % -> %".format(name, val).postln;
    }, '/music/gate');

    // /music/set  instrumentName  paramName  value
    OSCdef(\set, { |msg|
        var name  = msg[1].asSymbol;
        var param = msg[2].asSymbol;
        var val   = msg[3].asFloat;
        ~synths[name] !? { |syn| syn.set(param, val) };
        "[set]  %.% -> %".format(name, param, val).postln;
    }, '/music/set');

    "── music engine ready — start chat.py ──".postln;
};
)
