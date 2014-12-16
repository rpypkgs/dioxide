#include <math.h>

static float pi = M_PI;
static float pi2 = 2.0f * M_PI;

/* Normalized sinf, for values predivided by 2pi. */
float nsinf(float z) {
    int quadrant;
    unsigned flip;
    /* Put z within the range. */
    z *= 4;
    quadrant = floorf(z);
    z -= quadrant;

    if (quadrant & 1) {
        z = 1.0f - z;
    }
    flip = quadrant & 2;

    /* Do the actual integration. */
    // z = 0.5f * z * (3.0f - (z * z));
    z = 0.5f * z * (pi - z * z * (pi2 - 5.0f - z * z * (pi - 3.0f)));
    if (flip) {
        z = -z;
    }
    return z;
}

