import math
import sys
import time

from rpython.rlib.rarithmetic import intmask, r_singlefloat
from rpython.rlib import rgil
from rpython.rtyper.annlowlevel import llhelper
from rpython.rtyper.lltypesystem import lltype, rffi

import jack

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

    def generate(self, note, buf, nframes):
        step = note.pitch * self.config.inverseSampleRate

        for i in range(nframes):
            self.applyADSR(note)

            accumulator = 0.0
            for j, drawbar in enumerate(self.config.drawbars):
                if drawbar:
                    accumulator += pots[drawbar] * nsin(note.phase * drawbarPitches[j])

            note.phase += step
            while note.phase >= 1.0: note.phase -= 1.0

            # Divide by the number of drawbars.
            buf[i] += accumulator / len(self.config.drawbars) * note.volume


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

    def generate(self, note, buf, nframes):
        for i in range(nframes):
            self.applyADSR(note)

            growlbrato.rate = 80 if note.stage < SUSTAIN else 5

            # Step forward.
            pitch = note.pitch * growlbrato.step(self.config.inverseSampleRate, 1)
            step = pitch * self.config.inverseSampleRate

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

            buf[i] += result * note.volume


class Note(object):
    pitch = phase = volume = 0.0
    stage = ATTACK


_DIOXIDE = [None]
def getDioxide(): return _DIOXIDE[0]

def sampleRateCallback(srate, _):
    srate = intmask(srate)
    getDioxide().config.updateSampleRate(srate)
    return 0

def go(nframes, _):
    d = getDioxide()

    midiBuf = jack.port_get_buffer(d.midiPort, nframes)
    eventCount = intmask(jack.midi_get_event_count(midiBuf))
    if eventCount:
        with lltype.scoped_alloc(jack.midi_event_t) as event:
            for i in range(eventCount):
                jack.midi_event_get(event, midiBuf, i)
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

    # Update pitch only once per processing callback, after handling MIDI
    # events, before emitting samples.
    d.cleanAndUpdateNotes()
    if not len(d.notes): return 0

    waveBuf = rffi.cast(rffi.FLOATP,
                        jack.port_get_buffer(d.wavePort, nframes))
    metal = d.metal()
    doubleBuf = [0.0] * nframes
    for note in d.notes.itervalues():
        metal.generate(note, doubleBuf, intmask(nframes))
    for i in range(intmask(nframes)): waveBuf[i] = r_singlefloat(doubleBuf[i])
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
