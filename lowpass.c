#include <math.h>

#include "lowpass.h"

void setup_lowpass(struct lowpass *lp, double cutoff) {
    /* This is a one-time setup; we can afford to use doubles here. */
    double omega = atan(M_PI * cutoff);

    lp->x = lp->y = 0;
    lp->a = -(1.0 - omega) / (1.0 + omega);
    lp->b = (1.0 - lp->a) / 2.0;
}

float run_lowpass(struct lowpass *lp, float input) {
    float rv = lp->b * (input + lp->x) - lp->a * lp->y;
    lp->x = input;
    lp->y = rv;
    return rv;
}
