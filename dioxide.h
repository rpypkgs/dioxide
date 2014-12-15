#include <asoundlib.h>

#include <ladspa.h>

#include "SDL.h"
#include "SDL_audio.h"

struct lfo {
    double phase;

    double rate;
    double center;
    double amplitude;
};

struct lfof {
    float phase;

    float rate;
    float center;
    float amplitude;
};

struct ladspa_plugin {
    void *dl_handle;

    unsigned input, output;

    const LADSPA_Descriptor *desc;
    LADSPA_Handle handle;
    struct ladspa_plugin *next;
};

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
    void (*generate)(struct dioxide *d, struct note *note, float *buffer, unsigned count);
    void (*adsr)(struct dioxide *d, struct note *note);
};

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

    struct ladspa_plugin *available_plugins;
    struct ladspa_plugin *plugin_chain;

    struct element *metal;
};

double step_lfo(struct dioxide *d, struct lfo *lfo, unsigned count);
float step_lfof(struct dioxide *d, struct lfof *lfo, unsigned count);

void setup_plugins(struct dioxide *d);
void hook_plugins(struct dioxide *d);
void cleanup_plugins(struct dioxide *d);

struct ladspa_plugin* find_plugin_by_id(struct ladspa_plugin *plugin,
                                        unsigned id);

void setup_sequencer(struct dioxide *d);
void poll_sequencer(struct dioxide *d);
void solicit_connections(struct dioxide *d);

struct element uranium, titanium, lead;
