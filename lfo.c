#include <math.h>

#include "dioxide.h"

double step_lfo(struct dioxide *d, struct lfo *lfo, unsigned count) {
    double phase, step, retval;

    assert(lfo->rate);

    phase = lfo->phase;
    step = 2 * M_PI * lfo->rate * d->inverse_sample_rate;

    while (count--) {
        phase += step;
    }
    while (phase >= 2 * M_PI) {
        phase -= 2 * M_PI;
    }

    retval = lfo->amplitude * sin(phase) + lfo->center;

    lfo->phase = phase;

    return retval;
}

float step_lfof(struct dioxide *d, struct lfof *lfo, unsigned count) {
    float phase, step, retval;

    assert(lfo->rate);

    phase = lfo->phase;
    step = 2 * M_PI * lfo->rate * d->inverse_sample_rate;

    while (count--) {
        phase += step;
    }
    while (phase >= 2 * M_PI) {
        phase -= 2 * M_PI;
    }

    retval = lfo->amplitude * sin(phase) + lfo->center;

    lfo->phase = phase;

    return retval;
}
