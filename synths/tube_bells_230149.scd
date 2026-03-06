Routine {
    SynthDef('tube_bells', {
        |out=0, rev=0, gate=0, amp=0.45, density=0.15, brightness=0.6, sendAmt=0.95|
        var env, trig, freq, decay, sig, pan;
        env  = Linen.kr(gate, 4, 1, 6, 0);
        trig = Dust.kr(density);
        freq = TExpRand.kr(200 * brightness, 1800 * brightness, trig);
        decay = TExpRand.kr(3.5, 9.0, trig);
        pan  = TRand.kr(-0.7, 0.7, trig);
        sig  = Ringz.ar(Impulse.ar(0) + TDuty.ar(Drand([0.001],inf), trig), freq, decay);
        sig  = sig + Ringz.ar(Impulse.ar(0) + TDuty.ar(Drand([0.001],inf), trig), freq * 1.51, decay * 0.7);
        sig  = sig + Ringz.ar(Impulse.ar(0) + TDuty.ar(Drand([0.001],inf), trig), freq * 2.27, decay * 0.5);
        sig  = LeakDC.ar(sig);
        sig  = Pan2.ar(sig * amp * env * 0.3, pan);
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;
    s.sync;
    ~synths['tube_bells'] = Synth('tube_bells', ['rev', ~rev]);
    "tube_bells ready".postln;
}.play;