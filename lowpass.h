struct lowpass {
    float x, y, a, b;
};

void setup_lowpass(struct lowpass *lp, double cutoff);
float run_lowpass(struct lowpass *lp, float input);
