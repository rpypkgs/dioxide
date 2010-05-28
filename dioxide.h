#include <asoundlib.h>

#include <fftw3.h>

#include <ladspa.h>

#include "SDL.h"
#include "SDL_audio.h"

struct lfo {
    double phase;

    double rate;
    double center;
    double amplitude;
};

struct ladspa_plugin {
    void *dl_handle;

    unsigned input, output;

    LADSPA_Descriptor *desc;
    LADSPA_Handle handle;
    struct ladspa_plugin *next;
};

enum adsr {
    ADSR_ATTACK,
    ADSR_DECAY,
    ADSR_SUSTAIN,
    ADSR_RELEASE,
};

static double six_cents = 1.0034717485095028;
static double step_up = 1.0594630943592953;
static double step_down = 0.94387431268169353;
static double inv_log_2 = 1.4426950408889634;

struct dioxide {
    snd_seq_t *seq;

    struct SDL_AudioSpec spec;

    double volume;
    double phase;
    float pitch;
    signed short pitch_bend;
    unsigned notes[16];
    unsigned note_count;

    struct lfo vibrato;

    int rudess;
    double second_phase;

    float chorus_width;

    float lpf_cutoff;
    float lpf_resonance;

    enum adsr adsr_phase;
    float adsr_volume;

    struct ladspa_plugin *available_plugins;
    struct ladspa_plugin *plugin_chain;
};

double step_lfo(struct dioxide *d, struct lfo *lfo, unsigned count);

void setup_plugins(struct dioxide *d);
void hook_plugins(struct dioxide *d);
void cleanup_plugins(struct dioxide *d);

struct ladspa_plugin* find_plugin_by_id(struct ladspa_plugin *plugin,
                                        unsigned id);
