#include <complex.h>
#include <math.h>
#include <signal.h>
#include <stdlib.h>

#include <sys/time.h>

#include "dioxide.h"

static int time_to_quit = 0;
static unsigned long mma = 0, frame_length = 0;

void handle_sigint(int s) {
    time_to_quit = 1;
    printf("Caught SIGINT, quitting.\n");
}

void handle_sigalrm(int s) {
    printf("Average frame length: %lu (%d%%)\n",
        mma, mma * 100 / frame_length);
}

void update_adsr(struct dioxide *d);
void update_pitch(struct dioxide *d);
void write_sound(void *private, Uint8 *stream, int len);

void setup_sound(struct dioxide *d) {
    struct SDL_AudioSpec actual, *wanted = &d->spec;
    double temp;
    unsigned i;

    wanted->freq = 48000;
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

    d->volume = 0.7;

    d->attack_time = 0.001;
    d->decay_time = 0.001;
    d->release_time = 0.001;

    d->lpf_cutoff = d->spec.freq * 0.5;
    d->lpf_resonance = 4.0;

    frame_length = 1000 * 1000 * actual.samples / actual.freq;

    printf("Initialized basic synth parameters, frame length is %d usec\n",
        frame_length);

    d->front_buffer = malloc(actual.samples * sizeof(float));
    d->back_buffer = malloc(actual.samples * sizeof(float));
    d->delay_buffer_size = actual.freq * 5;
    d->delay_buffer = malloc(d->delay_buffer_size * sizeof(short));
}

void close_sound(struct dioxide *d) {
    SDL_PauseAudio(1);
    SDL_CloseAudio();

    free(d->front_buffer);
    free(d->back_buffer);
    free(d->delay_buffer);
}

void write_sound(void *private, Uint8 *stream, int len) {
    struct dioxide *d = private;
    double accumulator;
    unsigned i;
    int retval;
    int delay_write_head, delay_read_head;
    float *samples = d->front_buffer, *backburner = d->back_buffer, *ftemp;
    signed short short_temp, *buf = (signed short*)stream;
    struct timeval then, now;
    unsigned long timediff;
    struct ladspa_plugin *plugin;

    delay_write_head = d->delay_buffer_position;
    delay_read_head = delay_write_head +
        (d->delay_buffer_size - d->delay_buffer_samples);
    delay_read_head %= d->delay_buffer_size;

    gettimeofday(&then, NULL);

    /* Treat len and buf as counting shorts, not bytes.
     * Avoids cognitive dissonance in later code. */
    len /= 2;

    /* Update pitch only once per buffer. */
    update_pitch(d);

    plugin = d->plugin_chain;

    plugin->desc->connect_port(plugin->handle, plugin->output, samples);
    plugin->desc->run(plugin->handle, len);
#if 0
    printf("initialsamples = [\n");
    for (i = 0; i < len; i++) {
        printf("%f,\n", samples[i]);
    }
    printf("]\n");
#endif
    while (plugin->next) {
        plugin = plugin->next;

        /* Switch the names of the buffers, so that "samples" is always the
         * buffer being rendered to. */
        if (LADSPA_IS_INPLACE_BROKEN(plugin->desc->Properties)) {
            ftemp = backburner;
            backburner = samples;
            samples = ftemp;

            plugin->desc->connect_port(plugin->handle,
                plugin->input, backburner);
        } else {
            plugin->desc->connect_port(plugin->handle, plugin->input, samples);
        }

        plugin->desc->connect_port(plugin->handle, plugin->output, samples);
        plugin->desc->run(plugin->handle, len);
#if 0
        printf("samples = [\n");
        for (i = 0; i < len; i++) {
            printf("%f,\n", samples[i]);
        }
        printf("]\n");
#endif
    }

    for (i = 0; i < len; i++) {
        accumulator = samples[i];

        update_adsr(d);

        accumulator *= d->adsr_volume * d->volume * -32767;

        if (accumulator > 32767) {
            accumulator = 32767;
        } else if (accumulator < -32768) {
            accumulator = -32768;
        }

        short_temp = (signed short)accumulator;

        if (d->delay) {
            /* No feedforward, really. */
            d->delay_buffer[delay_write_head] = short_temp / 2;
            short_temp += d->delay_buffer[delay_read_head];
            d->delay_buffer[delay_read_head] /= 2;

            delay_read_head++;
            delay_read_head %= d->delay_buffer_size;
            delay_write_head++;
            delay_write_head %= d->delay_buffer_size;
        }

        *buf = short_temp;
        buf++;
    }

    d->delay_buffer_position = delay_write_head;

    gettimeofday(&now, NULL);

    while (now.tv_sec != then.tv_sec) {
        now.tv_sec--;
        now.tv_usec += 1000 * 1000;
    }

    timediff = now.tv_usec - then.tv_usec;
    mma = (9 * mma + timediff) / 10;

    if (timediff > (1000 * 1000 * len * d->inverse_sample_rate)) {
        printf("Long frame: %d usec\n", timediff);
    }
}

void update_adsr(struct dioxide *d) {
    switch (d->adsr_phase) {
        case ADSR_ATTACK:
            if (d->adsr_volume < 1.0) {
                d->adsr_volume += d->inverse_sample_rate / d->attack_time;
            } else {
                d->adsr_volume = 1.0;
                d->adsr_phase = ADSR_DECAY;
            }
            break;
        case ADSR_DECAY:
            if (d->adsr_volume > 0.88) {
                d->adsr_volume -= 0.12 * d->inverse_sample_rate
                    / d->decay_time;
            } else {
                d->adsr_volume = 0.88;
                d->adsr_phase = ADSR_SUSTAIN;
            }
            break;
        case ADSR_SUSTAIN:
            break;
        case ADSR_RELEASE:
            if (d->adsr_volume > 0.0) {
                d->adsr_volume -= 0.88 * d->inverse_sample_rate
                    / d->release_time;
            } else {
                d->adsr_volume = 0.0;
            }
            break;
        default:
            break;
    }
}

void update_pitch(struct dioxide *d) {
    double note, bend, target_pitch, ratio;

    if (!d->note_count) {
        return;
    }

    /* Split the pitch wheel into an upper and lower range. */
    if (d->pitch_bend >= 0) {
        bend = d->pitch_bend * (2.0 / 8192.0);
    } else {
        bend = d->pitch_bend * (12.0 / 8192.0);
    }

    note = d->notes[d->note_count - 1];
    note += bend;

    target_pitch = 440 * pow(2, (note - 69.0) / 12.0);

    ratio = target_pitch / d->pitch;

    if ((d->pitch < 20) ||
        ((step_up > ratio) && (ratio > step_down)) ||
        !d->gliss) {
        d->pitch = target_pitch;
    } else {
        d->pitch = pow(M_E, log(d->pitch) + log(ratio) * 0.5);
    }
}

int main() {
    struct dioxide *d = calloc(1, sizeof(struct dioxide));
    struct itimerval timer;
    int retval;

    signal(SIGINT, handle_sigint);
    signal(SIGALRM, handle_sigalrm);
    getitimer(ITIMER_REAL, &timer);
    timer.it_value.tv_sec = timer.it_interval.tv_sec = 5;
    setitimer(ITIMER_REAL, &timer, NULL);

    if (!d) {
        exit(EXIT_FAILURE);
    }

    /* Sound must be set up before plugins, to obtain sample rate. */
    setup_sound(d);
    setup_plugins(d);
    hook_plugins(d);
    setup_sequencer(d);

    SDL_PauseAudio(0);

    while (!time_to_quit) {
        poll_sequencer(d);

        if (!d->connected) {
            solicit_connections(d);
        }
    }

    close_sound(d);
    cleanup_plugins(d);

    retval = snd_seq_close(d->seq);

    free(d);
    exit(retval);
}
