Routine {
    SynthDef('bell_seq', {
        |out=0, rev=0, gate=0, amp=0.5, sendAmt=0.8|
        var env, sig, freq, trig;
        trig = Impulse.kr(2);
        freq = Demand.kr(trig, 0, Dseq([69, 72, 76, 81, 77, 72, 69, 65].midicps, inf));
        env = Ringz.ar(Impulse.ar(2), freq, 0.8) * amp;
        sig = Pan2.ar(env, SinOsc.kr(0.3));
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;
    s.sync;
    ~synths['bell_seq'] = Synth('bell_seq', ['rev', ~rev]);
    "bell_seq ready".postln;
}.play;