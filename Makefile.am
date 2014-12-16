bin_PROGRAMS = dioxide dioxide-benchmark

dioxide_benchmark_SOURCES = benchmark.c timer.c nsinf.c

dioxide_SOURCES = main.c lfo.c sequencer.c timer.c nsinf.c lowpass.c \
                  titanium.c uranium.c lead.c
dioxide_CFLAGS = $(ALSA_CFLAGS) $(SDL_CFLAGS)
dioxide_LDFLAGS = $(ALSA_LIBS) $(SDL_LIBS)
