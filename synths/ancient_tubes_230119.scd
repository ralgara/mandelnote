Routine {
    SynthDef('ancient_tubes', {
        |out=0, rev=0, gate=0, amp=0.5, sendAmt=0.9|
        var env, sig, toneA, toneB, toneC, noise, filtered, freq, pan, drift;

        // Long, slow envelope — breathlike
        env = Linen.kr(gate, 6, 1, 8, 0);

        // Three detuned resonant tubes — ratios suggest harmonic series but slightly off
        drift = LFNoise1.kr(0.07) * 3;
        freq  = 55 + drift;

        toneA = DynKlank.ar(
            `[ [1.0, 2.73, 4.89, 7.1], nil, [4.0, 3.2, 2.5, 1.8] ],
            PinkNoise.ar(0.015),
            freqscale: freq
        );

        toneB = DynKlank.ar(
            `[ [1.0, 1.93, 3.47, 5.82], nil, [5.0, 4.0, 3.0, 2.0] ],
            PinkNoise.ar(0.015),
            freqscale: freq * 1.007
        );

        toneC = DynKlank.ar(
            `[ [1.0, 3.14, 5.01, 8.33], nil, [3.5, 2.8, 2.0, 1.5] ],
            PinkNoise.ar(0.012),
            freqscale: freq * 0.994
        );

        // Blend and add a breath-noise layer
        noise    = BPF.ar(PinkNoise.ar(0.04), freq * 2.1 + LFNoise1.kr(0.12, 80), 0.15);
        filtered = (toneA + toneB + toneC) * 0.33 + noise;

        // Soft stereo spread with slow pan drift
        pan = LFNoise1.kr(0.04, 0.5);
        sig = Pan2.ar(filtered * amp * env, pan);

        Out.ar(out, sig);
        Out.ar(rev, sig * sendAmt);
    }).add;
    s.sync;

    // Intermittent trigger sequencer — irregular long tones
    ~synths['ancient_tubes'] = Synth('ancient_tubes', ['rev', ~rev]);

    ~tubes_seq = Task({
        var waitTime, onTime;
        loop {
            // Each breath: 4–14 seconds of silence, then 8–20 seconds of tone
            waitTime = rrand(4.0, 14.0);
            onTime   = rrand(8.0, 20.0);

            ~synths['ancient_tubes'].set('gate', 0);
            waitTime.wait;

            ~synths['ancient_tubes'].set('gate', 1);
            onTime.wait;
        }
    }).play;

    "ancient_tubes ready".postln;
}.play;