#include <complex.h>
#include <math.h>
#include <signal.h>
#include <stdlib.h>

#include <sys/time.h>

#include "dioxide.h"
#include "timer.h"

static int time_to_quit = 0;
static unsigned long frame_length = 0;

void handle_sigint(int s) {
    time_to_quit = 1;
    printf("Caught SIGINT, quitting.\n");
}

void update_pitch(struct dioxide *d);
void write_sound(void *private, Uint8 *stream, int len);

void setup_sound(struct dioxide *d) {
    struct SDL_AudioSpec actual, *wanted = &d->spec;
    double temp;
    unsigned i;

    wanted->freq = 44100;
    wanted->format = AUDIO_S16;
    wanted->channels = 1;
    wanted->samples = 512;
    wanted->callback = write_sound;
    wanted->userdata = d;

    if (SDL_OpenAudio(wanted, &actual)) {
        printf("Couldn't setup sound: %s\n", SDL_GetError());
        exit(EXIT_FAILURE);
    }

    printf("Opened sound for playback: Rate %d, format %d, samples %d\n",
        actual.freq, actual.format, actual.samples);

    wanted->freq = actual.freq;
    wanted->format = actual.format;
    wanted->samples = actual.samples;

    d->inverse_sample_rate = 1.0 / actual.freq;

    d->volume = 1.0;

    d->attack_time = 0.001;
    d->decay_time = 0.001;
    d->release_time = 0.001;

    d->lpf_cutoff = d->spec.freq * 0.5;
    d->lpf_resonance = 4.0;

    frame_length = 1000 * 1000 * actual.samples / actual.freq;

    printf("Initialized basic synth parameters, frame length is %ld usec\n",
        frame_length);

    d->front_buffer = malloc(actual.samples * sizeof(float));
    d->back_buffer = malloc(actual.samples * sizeof(float));

    d->metal = &titanium;
}

void close_sound(struct dioxide *d) {
    SDL_PauseAudio(1);
    SDL_CloseAudio();

    free(d->front_buffer);
    free(d->back_buffer);
}

void write_sound(void *private, Uint8 *stream, int len) {
    struct dioxide *d = private;
    struct note *note, *prev_note;
    double accumulator;
    unsigned i, polyphony = 0;
    int retval;
    float *samples = d->front_buffer, *backburner = d->back_buffer, *ftemp;
    signed short short_temp, *buf = (signed short*)stream;
    struct timeval then, now;
    unsigned long timediff;

    gettimeofday(&then, NULL);

    if (!d->notes->next) {
        SDL_PauseAudio(1);
        return;
    }

    for (prev_note = d->notes, note = prev_note->next; note; prev_note = note, note = note->next) {
        if (note->adsr_volume == 0.0 && note->adsr_phase == ADSR_RELEASE) {
            prev_note->next = note->next;
            free(note);
            note = prev_note;
        }
    }

    if (!d->notes->next) {
        SDL_PauseAudio(1);
        return;
    }

    /* Treat len and buf as counting shorts, not bytes.
     * Avoids cognitive dissonance in later code. */
    len /= 2;

    /* Update pitch only once per buffer. */
    update_pitch(d);

    memset(samples, 0, len * sizeof(float));

    for (note = d->notes->next; note; note = note->next) {
        d->metal->generate(d, note, samples, len);
        polyphony++;
    }

#if 0
    printf("initialsamples = [\n");
    for (i = 0; i < len; i++) {
        printf("%f,\n", samples[i]);
    }
    printf("]\n");
#endif

    for (i = 0; i < len; i++) {
        accumulator = samples[i];

        accumulator *= d->volume * -32767;

        if (accumulator > 32767) {
            accumulator = 32767;
        } else if (accumulator < -32768) {
            accumulator = -32768;
        }

        short_temp = (signed short)accumulator;

        *buf = short_temp;
        buf++;
    }

    timediff = us(then);

    if (timediff > frame_length) {
        printf("Long frame: %ldus (%ldus alloted)\n", timediff, frame_length);
    }
}

void update_pitch(struct dioxide *d) {
    struct note *note = d->notes->next;
    double midi, bend, target_pitch, ratio;

    while (note) {
        switch (d->pitch_wheel_config) {
            case WHEEL_TRADITIONAL:
                bend = d->pitch_bend * (2.0 / 8192.0);
                break;
            case WHEEL_RUDESS:
                /* Split the pitch wheel into an upper and lower range. */
                if (d->pitch_bend >= 0) {
                    bend = d->pitch_bend * (2.0 / 8192.0);
                } else {
                    bend = d->pitch_bend * (12.0 / 8192.0);
                }
                break;
            case WHEEL_DIVEBOMB:
                if (d->pitch_bend >= 0) {
                    bend = d->pitch_bend * (24.0 / 8192.0);
                } else {
                    bend = d->pitch_bend * (36.0 / 8192.0);
                }
                break;
        }

        midi = note->note + bend;

        note->pitch = 440 * pow(2, (midi - 69.0) / 12.0);
        note = note->next;
    }
}

int main() {
    struct dioxide *d = calloc(1, sizeof(struct dioxide));
    d->notes = calloc(1, sizeof(struct note));
    struct itimerval timer;
    int retval;

    signal(SIGINT, handle_sigint);

    if (!d) {
        exit(EXIT_FAILURE);
    }

    setup_sound(d);
    setup_sequencer(d);

    SDL_PauseAudio(1);

    while (!time_to_quit) {
        poll_sequencer(d);

        if (!d->connected) {
            solicit_connections(d);
        }
    }

    close_sound(d);

    retval = snd_seq_close(d->seq);

    free(d->notes);
    free(d);
    exit(retval);
}
