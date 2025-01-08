import math
import sys
import time

from rpython.rlib.rarithmetic import intmask, r_singlefloat
from rpython.rlib.unroll import unrolling_iterable
from rpython.rlib import rgil
from rpython.rtyper.annlowlevel import llhelper
from rpython.rtyper.lltypesystem import lltype, rffi

import jack

def lerp(x, y, t): return (1.0 - t) * x + t * y

# lolremez: sin(sqrt(x))/sqrt(x) on [0, pi/2]
SINE_COEFFS = (2.5904885005360522e-06, -0.00019800897762795432,
               0.008332899823351751, -0.16666647634639714, 0.999999976589882)
def horner(z):
    rv = 0.0
    for c in unrolling_iterable(SINE_COEFFS): rv = rv * z + c
    return rv
def fastsin(z): return z * horner(z * z)
HPI = math.pi / 2.0
def nsin(z):
    "Normalized sine; like math.sin(x) where z = x / 2pi."

    # Put z within the range.
    z, quadrant = math.modf(z * 4)
    quadrant = int(quadrant)

    if quadrant & 1: z = 1.0 - z
    flip = bool(quadrant & 2)

    # Do the actual integration.
    z = fastsin(z * HPI)
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

TRADITIONAL, RUDESS, DIVEBOMB = range(3)

class Config(object):
    elementIndex = 0
    volume = 1.0
    attackTime = decayTime = releaseTime = 0.001
    lpfResonance = 4.0
    pitchWheel = 0
    pitchWheelConfig = TRADITIONAL

    def __init__(self): self.drawbars = [0] * 9

    def updateSampleRate(self, srate):
        print "Sample rate: %d" % srate
        self.inverseSampleRate = 1.0 / srate
        self.lpfCutoff = srate

    def computeBend(self):
        if self.pitchWheelConfig == TRADITIONAL:
            return self.pitchWheel * (2.0 / 8192.0)
        elif self.pitchWheelConfig == RUDESS:
            # Split the pitch wheel into an upper and lower range.
            if self.pitchWheel >= 0:
                return self.pitchWheel * (2.0 / 8192.0)
            else: return self.pitchWheel * (12.0 / 8192.0)
        elif self.pitchWheelConfig == DIVEBOMB:
            if self.pitchWheel >= 0:
                return self.pitchWheel * (24.0 / 8192.0)
            else: return self.pitchWheel * (36.0 / 8192.0)
        assert False

    # Oxygen pots and dials all go from 0 to 127.
    def handleController(self, control, value):
        # C1
        if control == 74:
            self.drawbars[0] = scalePotLong(value, 0, 8)
        # C2
        elif control == 71:
            self.drawbars[1] = scalePotLong(value, 0, 8)
        # C3
        elif control == 91:
            self.drawbars[2] = scalePotLong(value, 0, 8)
        # C4
        elif control == 93:
            self.drawbars[3] = scalePotLong(value, 0, 8)
        # C5
        elif control == 73:
            self.drawbars[4] = scalePotLong(value, 0, 8)
        # C6
        elif control == 72:
            self.drawbars[5] = scalePotLong(value, 0, 8)
        # C7
        elif control == 5:
            self.drawbars[6] = scalePotLong(value, 0, 8)
        # C8
        elif control == 84:
            self.drawbars[7] = scalePotLong(value, 0, 8)
        # C9
        elif control == 7:
            self.drawbars[8] = scalePotLong(value, 0, 8)
        # C10
        elif control == 75:
            self.volume = scalePotFloat(value, 0.0, 1.0)
        # C11
        elif control == 76:
            self.attackTime = scalePotFloat(value, 0.001, 1.0)
        # C12
        elif control == 92:
            self.decayTime = scalePotFloat(value, 0.001, 1.0)
        # C13
        elif control == 95:
            self.releaseTime = scalePotFloat(value, 0.001, 1.0)
        # C14
        elif control == 10:
            self.chorusDelay = scalePotLogFloat(value, 2.5, 40)
            self.lpfResonance = scalePotFloat(value, 0.0, 4.0)
        # C15
        elif control == 77:
            self.phaserRate = scalePotFloat(value, 0.0, 1.0)
            self.phaserDepth = scalePotFloat(value, 0.0, 1.0)
        # C16
        elif control == 78:
            self.phaserSpread = scalePotFloat(value, 0.0, 1.5708)
        # C16
        elif control == 79:
            self.phaserFeedback = scalePotFloat(value, 0.0, 0.999)
        # C34
        elif control == 1:
            self.modWheel = scalePotFloat(value, 0.001, 1.0)
        else: print "Controller %d, value %d" % (control, value)

    def handleProgramChange(self, value):
        # C18-C19
        if 0 <= value <= 1: self.elementIndex = value
        # C20
        elif value == 2: pass
        # C21
        elif value == 3:
            self.pitchWheelConfig = (self.pitchWheelConfig + 1) % 3
        else: print "Program Change %d" % value


ATTACK, DECAY, SUSTAIN, RELEASE = range(4)

class Element(object):
    def __init__(self, config):
        assert self.name
        self.config = config

    def attack(self, note): pass
    def decay(self, note): pass
    def sustain(self, note): pass
    def release(self, note): pass

    def applyADSR(self, note):
        if note.stage == ATTACK: return self.attack(note)
        elif note.stage == DECAY: return self.decay(note)
        elif note.stage == SUSTAIN: return self.sustain(note)
        elif note.stage == RELEASE: return self.release(note)
        else: assert False


# Titanium: Hammond-style organ

# These are technically twice the correct frequency. It makes the maths a bit
# easier conceptually.
drawbarPitches = [0.5, 1.5, 1, 2, 3, 4, 5, 6, 8]
pots = [1.0 / (2 ** k) for k in range(9)]

class Titanium(Element):
    name = "Titanium"
    peak = 1.0

    def attack(self, note):
        if note.volume < self.peak:
            note.volume += self.config.inverseSampleRate / self.config.attackTime
        else:
            note.volume = self.peak
            note.stage = SUSTAIN

    def release(self, note):
        if note.volume > 0.0:
            note.volume -= self.peak * self.config.inverseSampleRate / self.config.releaseTime
        else: note.volume = 0.0

    def generate(self, note):
        step = note.pitch * self.config.inverseSampleRate
        note.addPhase(step)

        accumulator = 0.0
        for j, drawbar in enumerate(self.config.drawbars):
            if drawbar:
                accumulator += pots[drawbar] * nsin(note.phase * drawbarPitches[j])

        # Divide by the number of drawbars.
        return accumulator / len(self.config.drawbars) * note.volume


# Uranium: sawtooth lead

# A wavetable for a sawtooth wave.
# The table cuts off at 1/3 of the sample rate, rather than the Nyquist 1/2,
# to create a smoother-sounding rolloff.
SAW_BOT = 65.0 # approx. C2
SAW_TOP = 2090.0 # approx. C7
# Round down, use even count, +1 for fundamental gives odd count.
def countHarms(cutoff, freq): return (int(cutoff / freq) >> 1) << 1
def makeTable(size, harmCount):
    print "Table: size %d, %d harmonics" % (size, harmCount)
    d = float(size)
    rv = [0.0] * (size + 1)
    for i in range(size + 1):
        acc = 0.0
        for j in range(1, harmCount): acc += nsin(i * j / d) / j
        rv[i] = acc
    return rv
class TableSaw(object):
    size = 1024
    upper = lower = [0.0] * (size + 1)

    def updateSampleRate(self, srate):
        max_j = srate / 3.0
        self.upper = makeTable(self.size, countHarms(max_j, SAW_TOP))
        self.lower = makeTable(self.size, countHarms(max_j, SAW_BOT))

    def sample(self, pitch, phase):
        # Do our sampling from the wavetable.
        t, index = math.modf(phase * self.size)
        index = int(index)
        upper = lerp(self.upper[index], self.upper[index + 1], t)
        lower = lerp(self.lower[index], self.lower[index + 1], t)
        # And interpolate the samples.
        if pitch < SAW_BOT: return lower
        if pitch > SAW_TOP: return upper
        return lerp(lower, upper, (pitch - SAW_BOT) / SAW_TOP)
tableSaw = TableSaw()

growlbrato = LFO(80, 1, 1.0 / 288)

class Uranium(Element):
    name = "Uranium"
    peak = 1.0
    sustained = 0.4

    def attack(self, note):
        if note.volume < self.peak:
            note.volume += self.config.inverseSampleRate / self.config.attackTime
        else:
            note.volume = self.peak
            note.stage = DECAY

    def decay(self, note):
        if note.volume > self.sustained:
            note.volume -= (self.peak - self.sustained) * self.config.inverseSampleRate / self.config.decayTime
        else:
            note.volume = self.sustained
            note.stage = SUSTAIN

    def release(self, note):
        if note.volume > 0.0:
            note.volume -= self.sustained * self.config.inverseSampleRate / self.config.releaseTime
        else: note.volume = 0.0

    def generate(self, note):
        growlbrato.rate = 80 if note.stage < SUSTAIN else 5

        # Step forward.
        pitch = note.pitch * growlbrato.step(self.config.inverseSampleRate, 1)
        step = pitch * self.config.inverseSampleRate
        note.addPhase(step)
        return tableSaw.sample(pitch, note.phase) * note.volume


class Note(object):
    pitch = phase = volume = 0.0
    stage = ATTACK

    def addPhase(self, step):
        phase = self.phase + step
        if phase >= 1.0: phase -= 1.0
        self.phase = phase


_DIOXIDE = [None]
def getDioxide(): return _DIOXIDE[0]

def sampleRateCallback(srate, _):
    srate = intmask(srate)
    getDioxide().config.updateSampleRate(srate)
    tableSaw.updateSampleRate(srate)
    return 0

def go(nframes, _):
    d = getDioxide()
    metal = d.metal()

    midiBuf = jack.port_get_buffer(d.midiPort, nframes)
    eventCount = intmask(jack.midi_get_event_count(midiBuf))
    moreEvents = bool(eventCount)
    eventIndex = 0
    nextEventFrame = 0

    waveBuf = rffi.cast(rffi.FLOATP,
                        jack.port_get_buffer(d.wavePort, nframes))
    with lltype.scoped_alloc(jack.midi_event_t) as event:
        for i in range(intmask(nframes)):
            if nextEventFrame <= i and moreEvents:
                jack.midi_event_get(event, midiBuf, eventIndex)
                while intmask(event.c_time) <= i:
                    ty = intmask(event.c_buffer[0]) >> 4
                    if ty == 8:
                        midiNote = intmask(event.c_buffer[1])
                        if midiNote in d.notes: d.notes[midiNote].stage = RELEASE
                    elif ty == 9:
                        midiNote = intmask(event.c_buffer[1])
                        if midiNote in d.notes: d.notes[midiNote].stage = ATTACK
                        else: d.notes[midiNote] = Note()
                    elif ty == 11:
                        d.config.handleController(intmask(event.c_buffer[1]),
                                                  intmask(event.c_buffer[2]))
                    elif ty == 12:
                        d.config.handleProgramChange(intmask(event.c_buffer[1]))
                    elif ty == 14:
                        low = intmask(event.c_buffer[1])
                        high = intmask(event.c_buffer[2])
                        d.config.pitchWheel = ((high << 7) | low) - 0x1fff
                    else: print "Unknown MIDI event type %d" % ty

                    eventIndex += 1
                    if eventCount <= eventIndex:
                        moreEvents = False
                        break
                    jack.midi_event_get(event, midiBuf, eventIndex)
                nextEventFrame = intmask(event.c_time)

            acc = 0.0
            for note in d.notes.itervalues():
                metal.applyADSR(note)
                acc += metal.generate(note)
            waveBuf[i] = r_singlefloat(acc)

    # Recompute pitches and discard released notes.
    d.cleanAndUpdateNotes()
    return 0

class Dioxide(object):
    def __init__(self):
        self.config = Config()
        self.notes = {}
        self.elements = [Uranium(self.config), Titanium(self.config)]

    def cleanAndUpdateNotes(self):
        done = []
        for midiNote, note in self.notes.items():
            if note.volume == 0.0 and note.stage == RELEASE:
                done.append(midiNote)
            else:
                midi = midiNote + self.config.computeBend()
                note.pitch = 440.0 * math.pow(2, (midi - 69.0) / 12.0)
        for midiNote in done: del self.notes[midiNote]

    def metal(self): return self.elements[self.config.elementIndex]

    def setup(self):
        self.client = jack.client_open("dioxide", 0, None)
        if not self.client:
            print "Couldn't connect to JACK!"
            return False

        self.name = rffi.charp2str(jack.get_client_name(self.client))
        print "Registered with JACK as '%s'" % self.name

        self.config.updateSampleRate(intmask(jack.get_sample_rate(self.client)))

        jack.set_sample_rate_callback(self.client, sampleRateCallback, None)
        jack.set_process_callback(self.client, go, None)

        self.midiPort = jack.port_register(self.client, "MIDI in",
                                           jack.DEFAULT_MIDI_TYPE,
                                           jack.PortIsInput, 0)
        self.wavePort = jack.port_register(self.client, "wave out",
                                           jack.DEFAULT_AUDIO_TYPE,
                                           jack.PortIsOutput, 0)
        return True

    def start(self):
        if jack.activate(self.client):
            print "Couldn't activate JACK client!"
            return
        while True: time.sleep(5)

    def teardown(self): return jack.client_close(self.client)
_DIOXIDE[0] = Dioxide()


def main(argv):
    # Explicitly enable the GIL. RPython cannot otherwise detect that we will
    # need it until it is too late and we are already crashing.
    rgil.allocate()

    d = getDioxide()
    print "Setting up JACK client..."
    if not d.setup(): return 1

    print "Starting main loop..."
    try: d.start()
    except KeyboardInterrupt: pass

    return d.teardown()

def target(driver, *args):
    driver.exe_name = "dioxide"
    return main, None

if __name__ == "__main__": sys.exit(main(sys.argv))
