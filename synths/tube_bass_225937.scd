Routine {
    SynthDef('tube_bass', {
        |out=0, rev=0, gate=0, amp=0.5, freq=45.0, detune=0.3, atk=3.0, rel=6.0, sendAmt=0.9|
        var env, sig, a, b, filtered, verb;
        env = Linen.kr(gate, atk, 1, rel, 2);
        a = SinOsc.ar(freq * (1 - (detune * 0.01)));
        b = SinOsc.ar(freq * (1 + (detune * 0.01)) * 2.0, 0, 0.3);
        sig = (a + b) * env * amp;
        filtered = BPF.ar(sig, freq * 3.5, 0.6) + (sig * 0.5);
        filtered = filtered + CombC.ar(filtered, 0.5, 0.23, 3.5, 0.35);
        filtered = Pan2.ar(filtered, 0);
        Out.ar(out, filtered);
        Out.ar(rev, filtered * sendAmt);
    }).add;
    s.sync;
    ~synths['tube_bass'] = Synth('tube_bass', ['rev', ~rev]);
    "tube_bass ready".postln;
}.play;