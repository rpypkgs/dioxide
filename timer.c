#include "timer.h"

unsigned long us(struct timeval then) {
    struct timeval now;

    gettimeofday(&now, NULL);

    /* Here we are, as usual, hoping that this doesn't last for more than one
     * or two seconds. */
    while (now.tv_sec != then.tv_sec) {
        now.tv_sec--;
        now.tv_usec += 1000 * 1000;
    }

    return now.tv_usec - then.tv_usec;
}
