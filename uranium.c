#include <math.h>
#include <stdio.h>

#include "dioxide.h"
#include "lfo.h"
#include "nsinf.h"

static struct lfo growlbrato = {
    .rate = 80,
    .center = 1,
    .amplitude = 0.0034717485095028,
};

void generate_uranium(struct dioxide *d, struct note *note, float *buffer, unsigned size)
{
    float step, growl_adjustment, pitch, accumulator;
    unsigned i, j, max_j;

    for (i = 0; i < size; i++) {
        accumulator = 0;

        d->metal->adsr(d, note);

        if (note->adsr_phase < ADSR_SUSTAIN) {
            growlbrato.rate = 80;
        } else {
            growlbrato.rate = 5;
        }

        pitch = note->pitch * step_lfo(d, &growlbrato, 1);

        step = pitch * d->inverse_sample_rate;

        /* Weird things I've discovered.
         * BLITs aren't necessary. This is strictly additive.
         *
         * If the number of additions is above 120 or so, stuff gets really
         * shitty-sounding. The magic number of 129 should suffice for most
         * things.
         *
         * If the number of additions is even, everything goes to shit. This
         * helped: http://www.music.mcgill.ca/~gary/307/week5/bandlimited.html
         */
        max_j = d->spec.freq / note->pitch / 3;
        if (max_j > 11) {
            max_j = 11;
        } else if (!(max_j % 2)) {
            max_j--;
        }

        for (j = 1; j < max_j; j++) {
            accumulator += nsinf(note->phase * j) / j;
        }

        note->phase += step;

        while (note->phase >= 1.0) {
            note->phase -= 1.0;
        }

        *buffer += accumulator * note->adsr_volume;
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
    generate_uranium,
    adsr_uranium,
};
