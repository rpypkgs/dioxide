#include <math.h>
#include <stdio.h>

#include "dioxide.h"
#include "lfo.h"
#include "nsinf.h"

float lerp(float x, float y, float t) {
    return (1.0f - t) * x + t * y;
}


/* Weird things I've discovered.
 * BLITs aren't necessary. This is strictly additive.
 *
 * If the number of additions is above 120 or so, stuff gets really
 * shitty-sounding. The magic number of 129 should suffice for most things.
 *
 * max_j = d->spec.freq / note->pitch / 3;
 *
 * If the number of additions is even, everything goes to shit. This helped:
 * http://www.music.mcgill.ca/~gary/307/week5/bandlimited.html
 */
static float sawtooth[1025];
static unsigned inited = 0;

void setup_uranium() {
    int i, j;

    if (inited) {
        return;
    }

    for (i = 0; i <= 1025; i++) {
        sawtooth[i] = 0.0f;
        for (j = 1; j < 19; j++) {
            sawtooth[i] += nsinf(i * j / 1024.0f) / j;
        }
    }
    inited = 1;
}

static struct lfo growlbrato = {
    .rate = 80,
    .center = 1,
    .amplitude = 0.0034717485095028,
};

void generate_uranium(struct dioxide *d, struct note *note, float *buffer, unsigned size)
{
    float step, phase, pitch, t, result;
    unsigned i, index;

    for (i = 0; i < size; i++) {
        d->metal->adsr(d, note);

        if (note->adsr_phase < ADSR_SUSTAIN) {
            growlbrato.rate = 80;
        } else {
            growlbrato.rate = 5;
        }

        /* Step forward. */
        pitch = note->pitch * step_lfo(d, &growlbrato, 1);
        step = pitch * d->inverse_sample_rate;

        /* Update phase. */
        phase = note->phase + step;
        while (phase >= 1.0) {
            phase -= 1.0;
        }
        note->phase = phase;

        /* Do our sampling from the wavetable. */
        phase *= 1024.0f;
        index = phase;
        t = phase - index;
        result = lerp(sawtooth[index], sawtooth[index + 1], t);

        *buffer += result * note->adsr_volume;
        buffer++;
    }
}

void adsr_uranium(struct dioxide *d, struct note *note) {
    static float peak = 1.0, sustain = 0.4;
    switch (note->adsr_phase) {
        case ADSR_ATTACK:
            if (note->adsr_volume < peak) {
                note->adsr_volume += d->inverse_sample_rate / d->attack_time;
            } else {
                note->adsr_volume = peak;
                note->adsr_phase = ADSR_DECAY;
            }
            break;
        case ADSR_DECAY:
            if (note->adsr_volume > sustain) {
                note->adsr_volume -= (peak - sustain) * d->inverse_sample_rate
                    / d->decay_time;
            } else {
                note->adsr_volume = sustain;
                note->adsr_phase = ADSR_SUSTAIN;
            }
            break;
        case ADSR_SUSTAIN:
            break;
        case ADSR_RELEASE:
            if (note->adsr_volume > 0.0) {
                note->adsr_volume -= sustain * d->inverse_sample_rate
                    / d->release_time;
            } else {
                note->adsr_volume = 0.0;
            }
            break;
        default:
            break;
    }
}

struct element uranium = {
    "Uranium",
    setup_uranium,
    generate_uranium,
    adsr_uranium,
};
