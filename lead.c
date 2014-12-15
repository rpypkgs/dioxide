#include <math.h>
#include <stdio.h>

#include "dioxide.h"
#include "timer.h"

/* These are technically twice the correct frequency. It makes the maths a bit
 * easier conceptually. */
static float drawbar_pitches[9] = {
    0.5,
    1.5,
    1,
    2,
    3,
    4,
    5,
    6,
    8,
};

static float pots[] = {
    1.0 / 256.0,
    1.0 / 128.0,
    1.0 / 64.0,
    1.0 / 32.0,
    1.0 / 16.0,
    1.0 / 8.0,
    1.0 / 4.0,
    1.0 / 2.0,
    1.0 / 1.0,
};

void generate_lead(struct dioxide *d, struct note *note, float *buffer, unsigned size)
{
    static unsigned t = 0;
    struct timeval then;

    float step, accumulator;
    unsigned i, j;

    step = 2 * M_PI * note->pitch * d->inverse_sample_rate;

    for (i = 0; i < size; i++) {
        if (!t) {
            gettimeofday(&then, NULL);
        }

        accumulator = 0.0;

        d->metal->adsr(d, note);

        for (j = 0; j < 9; j++) {
            if (d->drawbars[j]) {
                accumulator += pots[d->drawbars[j]] *
                    sinf(note->phase * drawbar_pitches[j]);
            }
        }

        note->phase += step;

        while (note->phase > 2 * M_PI) {
            note->phase -= 2 * M_PI;
        }

        /* Divide by the number of drawbars. */
        *buffer += accumulator / 9.0 * note->adsr_volume;
        buffer++;

        if (!t) {
            t = 100000;
            printf("took %ldus\n", us(then));
        }
        t--;
    }
}

void adsr_lead(struct dioxide *d, struct note *note) {
    static float peak = 1.0;
    switch (note->adsr_phase) {
        case ADSR_ATTACK:
            if (note->adsr_volume < peak) {
                note->adsr_volume += d->inverse_sample_rate / d->attack_time;
            } else {
                note->adsr_volume = peak;
                note->adsr_phase = ADSR_SUSTAIN;
            }
            break;
        case ADSR_SUSTAIN:
            break;
        case ADSR_RELEASE:
            if (note->adsr_volume > 0.0) {
                note->adsr_volume -= peak * d->inverse_sample_rate
                    / d->release_time;
            } else {
                note->adsr_volume = 0.0;
            }
            break;
        default:
            break;
    }
}

struct element lead = {
    generate_lead,
    adsr_lead,
};
