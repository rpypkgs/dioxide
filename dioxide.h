#ifndef DIOXIDE_H
#define DIOXIDE_H

#include <alsa/asoundlib.h>

#include "SDL.h"
#include "SDL_audio.h"

enum adsr {
    ADSR_ATTACK,
    ADSR_DECAY,
    ADSR_SUSTAIN,
    ADSR_RELEASE,
};

enum wheel_config {
    WHEEL_TRADITIONAL,
    WHEEL_RUDESS,
    WHEEL_DIVEBOMB,
    WHEEL_MAX,
};

static double six_cents = 1.0034717485095028;
static double twelve_cents = 1.0069555500567189;
static double step_up = 1.0594630943592953;
static double step_down = 0.94387431268169353;

struct dioxide;

struct note {
    unsigned note;
    float pitch;
    double phase;

    enum adsr adsr_phase;
    float adsr_volume;

    struct note *next;
};

struct element {
    char *name;
    void (*setup)();
    void (*generate)(struct dioxide *d, struct note *note, float *buffer, unsigned count);
    void (*adsr)(struct dioxide *d, struct note *note);
};

void change_element(struct dioxide *d, struct element *element);

struct dioxide {
    snd_seq_t *seq;
    int seq_port;
    int connected;

    struct SDL_AudioSpec spec;
    float inverse_sample_rate;

    double volume;
    double phase;

    struct note *notes;

    enum wheel_config pitch_wheel_config;
    signed short pitch_bend;

    float *front_buffer, *back_buffer;

    float mod_wheel;

    float chorus_delay;

    float phaser_rate;
    float phaser_depth;
    float phaser_spread;
    float phaser_feedback;

    float lpf_cutoff;
    float lpf_resonance;

    float attack_time;
    float decay_time;
    float release_time;

    short drawbars[9];

    struct element *metal;
};

void setup_sequencer(struct dioxide *d);
void poll_sequencer(struct dioxide *d);
void solicit_connections(struct dioxide *d);

#endif
