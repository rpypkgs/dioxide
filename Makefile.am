bin_PROGRAMS = dioxide dioxide-benchmark

dioxide_benchmark_SOURCES = benchmark.c timer.c nsinf.c

dioxide_SOURCES = main.c lfo.c sequencer.c timer.c nsinf.c lowpass.c \
                  titanium.c uranium.c
dioxide_CFLAGS = -fcommon $(ALSA_CFLAGS) $(SDL_CFLAGS)
dioxide_LDFLAGS = -fcommon $(ALSA_LIBS) $(SDL_LIBS)
