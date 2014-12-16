#include <math.h>
#include <stdlib.h>
#include <stdio.h>

#include "nsinf.h"
#include "timer.h"

#define START gettimeofday(&then, NULL); for (i = 0; i < 32768; i++)
#define STOP(x, f) printf(x ": %f (%ldus)\n", f, us(then) / 32);

static float pi = M_PI;
static float pi2 = 2.0f * M_PI;

static double epsilon = 1.0 / 4096.0;
static float epsilonf = 1.0f / 4096.0f;

int main() {
    struct timeval then;
    unsigned i;
    double d, acc;
    float f, accf;

    printf("%f %f %f\n", sin(M_PI / 4.0), sinf(pi / 4.0f), nsinf(0.125f));
    printf("%f %f %f\n", sin(M_PI * 3.0 / 4.0), sinf(pi * 3.0f / 4.0f), nsinf(0.375f));

    acc = 0.0;
    START {
        d = sin(acc);
        acc += epsilon;
    } STOP("sin", d)
    acc = 0.0;
    START {
        d = sin(acc);
        acc += epsilon;
    } STOP("sin (warm)", d)

    accf = 0.0f;
    START {
        f = sinf(accf);
        accf += epsilonf;
    } STOP("sinf", f)
    accf = 0.0f;
    START {
        f = sinf(accf);
        accf += epsilonf;
    } STOP("sinf (warm)", f)

    accf = 0.0f;
    START {
        f = nsinf(accf / pi2);
        accf += epsilonf;
        if (accf >= 1.0f) {
            accf -= 1.0f;
        }
    } STOP("nsinf", f)

    exit(EXIT_SUCCESS);
    return 0;
}
