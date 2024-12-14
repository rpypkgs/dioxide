import math
import sys
import time

from rpython.rlib.rarithmetic import intmask
from rpython.rlib.rerased import new_erasing_pair
from rpython.rtyper.annlowlevel import llhelper
from rpython.rtyper.lltypesystem import rffi
from rpython.rtyper.lltypesystem.lltype import scoped_alloc

from rsdl import RSDL

def lerp(x, y, t): return (1.0 - t) * x + t * y

pi2 = math.pi * 2

# Normalized sinf, for values predivided by 2pi.
def nsin(z):
    # Put z within the range.
    z, quadrant = math.modf(z * 4)
    quadrant = int(quadrant)

    if quadrant & 1: z = 1.0 - z
    flip = bool(quadrant & 2)

    # Do the actual integration.
    z = 0.5 * z * (math.pi - z * z * (pi2 - 5.0 - z * z * (math.pi - 3.0)))
    if flip: z = -z
    return z


class LowPass(object):
    x = y = 0.0

    def __init__(self, cutoff):
        omega = math.atan(math.pi * cutoff)
        self.a = -(1.0 - omega) / (1.0 + omega)
        self.b = (1.0 - self.a) / 2.0

    def run(self, i):
        rv = self.b * (i + self.x) - self.a * self.y
        self.x, self.y = i, rv
        return rv


class LFO(object):
    phase = 0.0

    def __init__(self, rate, center, amplitude):
        assert rate
        self.rate = rate
        self.center = center
        self.amplitude = amplitude

    def step(self, inverseSampleRate, count):
        step = self.rate * inverseSampleRate
        self.phase += step * count
        while self.phase >= 1.0: self.phase -= 1.0
        return self.amplitude * nsin(self.phase) + self.center


def scalePotLong(pot, low, high): return pot * (high - low) // 127 + low

def scalePotFloat(pot, low, high): return (pot / 127.0) * (high - low) + low

def scalePotLogFloat(pot, low, high):
    l = math.log(low)
    h = math.log(high)
    return math.exp((pot / 127.0) * (h - l) + l)

TRADITIONAL, RUDESS, DIVEBOMB, WHEEL_MAX = range(4)

class Config(object):
    elementIndex = 0
    volume = 1.0
    attackTime = decayTime = releaseTime = 0.001
    lpfResonance = 4.0
    pitchWheel = 0
    pitchWheelConfig = TRADITIONAL

    def computeBend(self):
        if self.config.pitchWheelConfig == TRADITIONAL:
            return self.config.pitchWheel * (2.0 / 8192.0)
        elif self.config.pitchWheel == RUDESS:
            # Split the pitch wheel into an upper and lower range.
            if self.pitchWheel >= 0:
                return self.config.pitchWheel * (2.0 / 8192.0)
            else: return self.config.pitchWheel * (12.0 / 8192.0)
        elif self.config.pitchWheel == DIVEBOMB:
            if self.pitchWheel >= 0:
                return self.config.pitchWheel * (24.0 / 8192.0)
            else: return self.config.pitchWheel * (36.0 / 8192.0)
        assert False

    # Oxygen pots and dials all go from 0 to 127.
    def handleController(self, control):
        # C1
        if control.param == 74:
            self.drawbars[0] = scalePotLong(control.value, 0, 8)
        # C2
        elif control.param == 71:
            self.drawbars[1] = scalePotLong(control.value, 0, 8)
        # C3
        elif control.param == 91:
            self.drawbars[2] = scalePotLong(control.value, 0, 8)
        # C4
        elif control.param == 93:
            self.drawbars[3] = scalePotLong(control.value, 0, 8)
        # C5
        elif control.param == 73:
            self.drawbars[4] = scalePotLong(control.value, 0, 8)
        # C6
        elif control.param == 72:
            self.drawbars[5] = scalePotLong(control.value, 0, 8)
        # C7
        elif control.param == 5:
            self.drawbars[6] = scalePotLong(control.value, 0, 8)
        # C8
        elif control.param == 84:
            self.drawbars[7] = scalePotLong(control.value, 0, 8)
        # C9
        elif control.param == 7:
            self.drawbars[8] = scalePotLong(control.value, 0, 8)
        # C10
        elif control.param == 75:
            self.volume = scalePotFloat(control.value, 0.0, 1.0)
        # C11
        elif control.param == 76:
            self.attackTime = scalePotFloat(control.value, 0.001, 1.0)
        # C12
        elif control.param == 92:
            self.decayTime = scalePotFloat(control.value, 0.001, 1.0)
        # C13
        elif control.param == 95:
            self.releaseTime = scalePotFloat(control.value, 0.001, 1.0)
        # C14
        elif control.param == 10:
            self.chorusDelay = scalePotLogFloat(control.value, 2.5, 40)
            self.lpfResonance = scalePotFloat(control.value, 0.0, 4.0)
        # C15
        elif control.param == 77:
            self.phaserRate = scalePotFloat(control.value, 0.0, 1.0)
            self.phaserDepth = scalePotFloat(control.value, 0.0, 1.0)
        # C16
        elif control.param == 78:
            self.phaserSpread = scalePotFloat(control.value, 0.0, 1.5708)
        # C16
        elif control.param == 79:
            self.phaserFeedback = scalePotFloat(control.value, 0.0, 0.999)
        # C34
        elif control.param == 1:
            self.modWheel = scalePotFloat(control.value, 0.001, 1.0)
        else: print "Controller %d, value %d" % (control.param, control.value)

    def handleProgramChange(self, value):
        # C18-C19
        if 0 <= value <= 1: self.elementIndex = value
        # C20
        elif value == 2: pass
        # C21
        elif value == 3:
            self.pitchWheelConfig = (self.pitchWheelConfig + 1) % WHEEL_MAX
        else: print "Program Change %d" % value


ATTACK, DECAY, SUSTAIN, RELEASE = range(4)

class ADSR(object):
    def __init__(self, inverseSampleRate):
        self.inverseSampleRate = inverseSampleRate
    def attack(self, note, attackTime): pass
    def decay(self, note, decayTime): pass
    def sustain(self, note): pass
    def release(self, note, releaseTime): pass

class Element(object):
    def __init__(self, inverseSampleRate):
        assert self.name
        self.inverseSampleRate = inverseSampleRate
        self.adsr = self.adsrCls(inverseSampleRate)

    def applyADSR(self, note, config):
        if note.stage == ATTACK:
            return self.adsr.attack(self.inverseSampleRate, note,
                                    config.attackTime)
        elif note.stage == DECAY:
            return self.adsr.decay(self.inverseSampleRate, note,
                                   config.decayTime)
        elif note.stage == SUSTAIN: return self.adsr.sustain(note)
        elif note.stage == RELEASE:
            return self.adsr.release(self.inverseSampleRate, note,
                                     config.releaseTime)
        else: assert False


# Titanium: Hammond-style organ

# These are technically twice the correct frequency. It makes the maths a bit
# easier conceptually.
drawbarPitches = [0.5, 1.5, 1, 2, 3, 4, 5, 6, 8]
pots = [1.0 / (2 ** k) for k in range(9)]

class ADSRTitanium(ADSR):
    peak = 1.0
    def attack(self, note, attackTime):
        if note.volume < self.peak:
            note.volume += self.inverseSampleRate / attackTime
        else:
            note.volume = self.peak
            note.stage = SUSTAIN
    def release(self, note, releaseTime):
        if note.volume > 0.0:
            note.volume -= self.peak * self.inverseSampleRate / releaseTime
        else: note.volume = 0.0

class Titanium(Element):
    name = "Titanium"
    adsrCls = ADSRTitanium

    def generate(self, note, config, buf):
        step = note.pitch * self.inverseSampleRate

        for i in range(len(buf)):
            self.applyADSR(note, config)

            accumulator = 0.0
            for j, drawbar in enumerate(config.drawbars):
                if drawbar:
                    accumulator += pots[drawbar] * nsin(note.phase * drawbarPitches[j])

            note.phase += step
            while note.phase >= 1.0: note.phase -= 1.0

            # Divide by the number of drawbars.
            buf[i] = accumulator / 9.0 * note.volume


# Uranium: sawtooth lead

# Weird things I've discovered.
# BLITs aren't necessary. This is strictly additive.
#
# If the number of additions is above 120 or so, stuff gets really
# shitty-sounding. The magic number of 129 should suffice for most things.
#
# max_j = d->spec.freq / note->pitch / 3;
#
# If the number of additions is even, everything goes to shit. This helped:
# http://www.music.mcgill.ca/~gary/307/week5/bandlimited.html
# XXX but the number of additions here is even?
sawtoothUpper = [sum([nsin(i * j / 1024.0) / j for j in range(1, 11)]) for i in range(1025)]
sawtoothLower = [sum([nsin(i * j / 1024.0) / j for j in range(1, 129)]) for i in range(1025)]

growlbrato = LFO(80, 1, 0.0034717485095028)

class ADSRUranium(ADSR):
    peak = 1.0
    sustain = 0.4
    def attack(self, note, attackTime):
        if note.volume < self.peak:
            note.volume += self.inverseSampleRate / attackTime
        else:
            note.volume = self.peak
            note.stage = DECAY
    def decay(self, note, decayTime):
        if note.volume > self.sustain:
            note.volume -= (self.peak - self.sustain) * self.inverseSampleRate / decayTime
        else:
            note.volume = self.sustain
            note.stage = SUSTAIN
    def release(self, note, releaseTime):
        if note.volume > 0.0:
            note.volume -= self.sustain * self.inverseSampleRate / releaseTime
        else: note.volume = 0.0

class Uranium(Element):
    name = "Uranium"
    adsrCls = ADSRUranium

    def generate(self, note, config, buf):
        for i in range(len(buf)):
            self.applyADSR(note, config)

            growlbrato.rate = 80 if note.stage < SUSTAIN else 5

            # Step forward.
            pitch = note.pitch * growlbrato.step(self.inverseSampleRate, 1)
            step = pitch * self.inverseSampleRate

            # Update phase.
            phase = note.phase + step
            while phase >= 1.0: phase -= 1.0
            note.phase = phase

            # Do our sampling from the wavetable.
            phase *= 1024.0
            t, index = math.modf(phase)
            index = int(index)
            upper = lerp(sawtoothUpper[index], sawtoothUpper[index + 1], t)
            lower = lerp(sawtoothLower[index], sawtoothLower[index + 1], t)

            # And interpolate the samples.
            if pitch < 220.0: result = lower
            elif pitch > 3520.0: result = upper
            else: result = lerp(lower, upper, (pitch - 220.0) / 3300.0)

            buf[i] = result * note.volume

_DIOXIDE = [None]
def getDioxide():
    if _DIOXIDE[0] is None: _DIOXIDE[0] = Dioxide()
    rv = _DIOXIDE[0]
    if rv is None: rv = _DIOXIDE[0] = Dioxide()
    return rv

def writeSound(_, stream, count):
    d = getDioxide()
    # Update pitch only once per buffer.
    d.cleanAndUpdateNotes()

    if not d.notes:
        RSDL.PauseAudio(1)
        return

    # Treat len and buf as counting shorts, not bytes.
    # Avoids cognitive dissonance in later code.
    count >>= 1
    stream = rffi.cast(rffi.SHORTP, stream)

    buf = [0.0] * count

    metal = d.metal()
    for note in d.notes: metal.generate(note, d.config, buf)

    for i, sample in enumerate(buf):
        acc = sample * d.config.volume * -32767
        acc = max(-32768, min(32767, acc))
        stream[i] = acc

class Dioxide(object):
    def __init__(self):
        self.config = Config()
        self.notes = []

    def cleanAndUpdateNotes(self):
        self.notes = [note for note in self.notes
                      if note.volume == 0.0 and note.stage == RELEASE]
        for note in self.notes:
            midi = note.note + self.config.computeBend()
            note.pitch = 440.0 * math.pow(2, (midi - 69.0) / 12.0)

    def metal(self): return self.elements[self.config.elementIndex]

    def setupSound(self):
        with scoped_alloc(RSDL.AudioSpec) as wanted:
            wanted.c_freq = rffi.r_int(44100)
            wanted.c_format = rffi.r_ushort(RSDL.AUDIO_S16)
            wanted.c_channels = rffi.r_uchar(1)
            wanted.c_samples = rffi.r_ushort(512)
            wanted.c_callback = llhelper(RSDL.AudioCallback, writeSound)

            with scoped_alloc(RSDL.AudioSpec) as actual:
                if RSDL.OpenAudio(wanted, actual):
                    print "Couldn't setup sound:", RSDL.GetError()
                    return False

                freq = intmask(actual.c_freq)
                samples = intmask(actual.c_samples)

                print "Opened sound for playback: Rate %d, format %d, samples %d" % (
                        freq, intmask(actual.c_format), samples)

                self.config.inverseSampleRate = 1.0 / freq
                self.config.lpfCutoff = freq

                print "Initialized basic synth params; frame length is %d usec" % (
                        1000 * 1000 * samples / freq)

        self.elements = [Uranium(self.config.inverseSampleRate),
                         Titanium(self.config.inverseSampleRate)]
        return True

def closeSound():
    RSDL.PauseAudio(1)
    RSDL.CloseAudio()


def main(argv):
    d = getDioxide()
    if not d.setupSound(): return 1
    # setupSequencer()

    RSDL.PauseAudio(1)

    try:
        while True:
            break
            # pollSequencer()
            # if connected: solicitConnections()
    except KeyboardInterrupt: pass

    closeSound()

    # retval = snd_seq_close(d->seq);

    return 0

def target(driver, *args):
    driver.exe_name = "dioxide"
    return main, None

if __name__ == "__main__": sys.exit(main(sys.argv))
