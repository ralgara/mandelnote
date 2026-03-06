Routine {
    SynthDef('test_melody', {
        |out=0, rev=0, gate=0, amp=0.5, sendAmt=0.4|
        var env, sig, osc;
        env = Linen.kr(gate, 2, 1, 2, 0);
        osc = SinOsc.ar(440, 0, 1);
        sig = Pan2.ar(osc * amp * env, 0);
        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;
    s.sync;
    ~synths['test_melody'] = Synth('test_melody', ['rev', ~rev]);
    "test_melody ready".postln;
}.play;