Routine {
    SynthDef('piano_tone', {
        |out=0, rev=0, gate=0, amp=0.5, freq=440, brightness=0.6, decay=2.8, sendAmt=0.7|
        var env, sig, hammer, body, pan;
        env = EnvGen.kr(Env.perc(0.004, decay, 1, -4), gate, doneAction: 0);
        hammer = HPF.ar(WhiteNoise.ar(0.3), 3000) * EnvGen.kr(Env.perc(0.001, 0.03), gate);
        body = Mix.ar([
            SinOsc.ar(freq, 0, 1.0),
            SinOsc.ar(freq * 2.0, 0, 0.4 * brightness),
            SinOsc.ar(freq * 3.01, 0, 0.2 * brightness),
            SinOsc.ar(freq * 4.02, 0, 0.08 * brightness)
        ]);
        sig = (body * env + (hammer * env)) * amp * 0.3;
        pan = Pan2.ar(sig, TRand.kr(-0.5, 0.5, gate));
        Out.ar(out, pan);
        Out.ar(rev, pan * sendAmt);
    }).add;
    s.sync;
    ~synths['piano_tone'] = Synth('piano_tone', ['rev', ~rev]);
    "piano_tone ready".postln;
}.play;