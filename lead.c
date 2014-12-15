#include <math.h>
#include <stdio.h>

#include "dioxide.h"
#include "timer.h"

static struct lfof growlbrato = {
    .rate = 80,
    .center = 1,
    /* six_cents - 1 */
    .amplitude = 0.0034717485095028,
};

struct lowpass {
    float x, y, a, b;
};

void setup_lowpass(struct lowpass *lp, double cutoff) {
    /* This is a one-time setup; we can afford to use doubles here. */
    double omega;

    lp->x = lp->y = 0;

    omega = atan(M_PI * cutoff);
    lp->a = -(1.0 - omega) / (1.0 + omega);
    lp->b = (1.0 - lp->a) / 2.0;
}

float run_lowpass(struct lowpass *lp, float input) {
    float rv = lp->b * (input + lp->x) - lp->a * lp->y;
    lp->x = input;
    lp->y = rv;
    return rv;
}

struct blit {
    float phase, attenuation, frequency, period, rolloff, rolloffPower;
    unsigned partials;
    struct lowpass lp;
};

void setup_blit(struct blit *blit, double attenuation, double cutoff) {
    /* This is a one-time setup; we can afford to use doubles here. */
    blit->phase = blit->frequency = blit->period = 0.0;
    blit->attenuation = attenuation;
    setup_lowpass(&blit->lp, cutoff);
}

float run_blit(struct blit *blit, float frequency) {
    float half_period, beta, beta_partials, cos_beta, numerator, denominator;
    float result;

    if (blit->phase >= 1.0 || blit->frequency == 0.0) {
        /* New cycle. Change the frequency and recalculate. */
        if (blit->phase >= 1.0) {
            blit->phase -= 1.0;
        }

        blit->frequency = frequency;
        blit->period = 1.0 / frequency;
        half_period = blit->period / 2.0;
        blit->partials = 1 + floorf(half_period);

        /* Recalculate rolloff. */
        blit->rolloff = powf(blit->attenuation, 1.0 / half_period);
        blit->rolloffPower = powf(blit->rolloff, blit->partials);
    }

    beta = M_PI * 2 * blit->phase;
    beta_partials = beta * blit->partials;
    cos_beta = cosf(beta);

    numerator = 1.0 - blit->rolloffPower * cosf(beta_partials)
        - blit->rolloff * (cos_beta - blit->rolloffPower * cosf(beta_partials - beta));
    denominator = blit->period * (1.0 + blit->rolloff * (-2.0 * cos_beta + blit->rolloff));

    blit->phase += blit->frequency;
    result = numerator / denominator - blit->frequency;

    return run_lowpass(&blit->lp, result);
}

void generate_lead(struct dioxide *d, struct note *note, float *buffer, unsigned size)
{
    static unsigned init = 0;
    static struct blit blit;
    
    static unsigned should_time = 0;
    float step, growl_adjustment, pitch, accumulator;
    unsigned i, j, max_j;
    struct timeval then;

    if (!init) {
        init = 1;
        setup_blit(&blit, 0.5, 0.0001);
    }

    for (i = 0; i < size; i++) {
        if (!should_time) {
            gettimeofday(&then, NULL);
        }

        accumulator = 0;

        d->metal->adsr(d, note);

        if (note->adsr_phase < ADSR_SUSTAIN) {
            growlbrato.rate = 80;
        } else {
            growlbrato.rate = 5;
        }

        pitch = note->pitch * step_lfof(d, &growlbrato, 1);

#if 0
        step = 2 * M_PI * pitch * d->inverse_sample_rate;

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
        if (max_j > 7) {
            max_j = 7;
        } else if (!(max_j % 2)) {
            max_j--;
        }

        for (j = 1; j < max_j; j++) {
            accumulator += sinf(note->phase * j) / j;
        }

        note->phase += step;

        while (note->phase > 2 * M_PI) {
            note->phase -= 2 * M_PI;
        }
#endif

        accumulator = run_blit(&blit, pitch);
        *buffer += accumulator * note->adsr_volume;
        buffer++;

        if (!should_time) {
            should_time += 10000;
            printf("Took %ldus to run a note\n", us(then));
        }
        should_time--;
    }
}

void adsr_lead(struct dioxide *d, struct note *note) {
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

struct element lead = {
    generate_lead,
    adsr_lead,
};
