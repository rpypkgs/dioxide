#include "lfo.h"
#include "nsinf.h"

float step_lfo(struct dioxide *d, struct lfo *lfo, unsigned count) {
    float phase, step, retval;

    assert(lfo->rate);

    phase = lfo->phase;
    step = lfo->rate * d->inverse_sample_rate;

    phase += step * count;
    while (phase >= 1.0) {
        phase -= 1.0;
    }

    retval = lfo->amplitude * nsinf(phase) + lfo->center;

    lfo->phase = phase;

    return retval;
}
