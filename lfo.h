#include "dioxide.h"

struct lfo {
    float phase;

    float rate;
    float center;
    float amplitude;
};

float step_lfo(struct dioxide *d, struct lfo *lfo, unsigned count);
