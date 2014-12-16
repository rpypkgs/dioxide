#include <math.h>

#include "dioxide.h"

long scale_pot_long(unsigned pot, long low, long high) {
    long l = pot * (high - low);

    return l / 127 + low;
}

float scale_pot_float(unsigned pot, float low, float high) {
    float f = pot / 127.0;

    return f * (high - low) + low;
}

float scale_pot_log_float(unsigned pot, float low, float high) {
    float f = pot / 127.0;

    low = log(low);
    high = log(high);

    f = f * (high - low) + low;

    return pow(M_E, f);
}

void handle_controller(struct dioxide *d, snd_seq_ev_ctrl_t control) {
    /* Oxygen pots and dials all go from 0 to 127. */
    switch (control.param) {
        /* C1 */
        case 74:
            d->drawbars[0] = scale_pot_long(control.value, 0, 8);
            break;
        /* C2 */
        case 71:
            d->drawbars[1] = scale_pot_long(control.value, 0, 8);
            break;
        /* C3 */
        case 91:
            d->drawbars[2] = scale_pot_long(control.value, 0, 8);
            break;
        /* C4 */
        case 93:
            d->drawbars[3] = scale_pot_long(control.value, 0, 8);
            break;
        /* C5 */
        case 73:
            d->drawbars[4] = scale_pot_long(control.value, 0, 8);
            break;
        /* C6 */
        case 72:
            d->drawbars[5] = scale_pot_long(control.value, 0, 8);
            break;
        /* C7 */
        case 5:
            d->drawbars[6] = scale_pot_long(control.value, 0, 8);
            break;
        /* C8 */
        case 84:
            d->drawbars[7] = scale_pot_long(control.value, 0, 8);
            break;
        /* C9 */
        case 7:
            d->drawbars[8] = scale_pot_long(control.value, 0, 8);
            break;
        /* C10 */
        case 75:
            d->volume = scale_pot_float(control.value, 0.0, 1.0);
            break;
        /* C11 */
        case 76:
            d->attack_time = scale_pot_float(control.value, 0.001, 1.0);
            break;
        /* C12 */
        case 92:
            d->decay_time = scale_pot_float(control.value, 0.001, 1.0);
            break;
        /* C13 */
        case 95:
            d->release_time = scale_pot_float(control.value, 0.001, 1.0);
            break;
        /* C14 */
        case 10:
            d->chorus_delay = scale_pot_log_float(control.value, 2.5, 40);
            d->lpf_resonance = scale_pot_float(control.value, 0.0, 4.0);
            break;
        /* C15 */
        case 77:
            d->phaser_rate = scale_pot_float(control.value, 0, 1);
            d->phaser_depth = scale_pot_float(control.value, 0, 1);
            break;
        /* C16 */
        case 78:
            d->phaser_spread = scale_pot_float(control.value, 0, 1.5708);
            break;
        /* C17 */
        case 79:
            d->phaser_feedback = scale_pot_float(control.value, 0, 0.999);
            break;
        /* C34 */
        case 1:
            d->mod_wheel = scale_pot_float(control.value, 0.001, 1.0);
            break;
        default:
            printf("Controller %d\n", control.param);
            printf("Value %d\n", control.value);
            break;
    }
}

void handle_program_change(struct dioxide *d, snd_seq_ev_ctrl_t control) {
    switch (control.value) {
        /* C18 */
        case 0:
            change_element(d, &titanium);
            break;
        /* C19 */
        case 1:
            change_element(d, &uranium);
            break;
        /* C20 */
        case 2:
            break;
        /* C21 */
        case 3:
            d->pitch_wheel_config = (d->pitch_wheel_config + 1) % WHEEL_MAX;
            break;
        default:
            printf("Program change %d\n", control.value);
            break;
    }
}

void poll_sequencer(struct dioxide *d) {
    snd_seq_event_t *event;
    enum snd_seq_event_type type;
    struct note *note;
    unsigned i, repeated = 0;

    if (snd_seq_event_input(d->seq, &event) == -EAGAIN) {
        return;
    }

    type = event->type;

    switch (type) {
        case SND_SEQ_EVENT_NOTEON:
            for (note = d->notes->next; note; note = note->next) {
                if (note->note == event->data.note.note) {
                    repeated = 1;
                    break;
                }
            }

            if (!note) {
                note = calloc(1, sizeof(struct note));
                note->next = d->notes->next;
                d->notes->next = note;
            }

            note->note = event->data.note.note;
            note->adsr_phase = ADSR_ATTACK;
            note->adsr_volume = 0.0;

            SDL_PauseAudio(0);

            break;
        case SND_SEQ_EVENT_NOTEOFF:
            for (note = d->notes->next; note; note = note->next) {
                if (note->note == event->data.note.note) {
                    note->adsr_phase = ADSR_RELEASE;
                }
            }

            break;
        case SND_SEQ_EVENT_CONTROLLER:
            handle_controller(d, event->data.control);
            break;
        case SND_SEQ_EVENT_PGMCHANGE:
            handle_program_change(d, event->data.control);
            break;
        case SND_SEQ_EVENT_PITCHBEND:
            d->pitch_bend = event->data.control.value;
            break;
        case SND_SEQ_EVENT_PORT_SUBSCRIBED:
            break;
        case SND_SEQ_EVENT_PORT_UNSUBSCRIBED:
            d->connected = 0;
            break;
        default:
            printf("Got event type %u\n", type);
            break;
    }
}

void solicit_connections(struct dioxide *d) {
    snd_seq_client_info_t *client_info;
    snd_seq_port_info_t *port_info;
    int caps, retval;

    snd_seq_client_info_alloca(&client_info);
    snd_seq_port_info_alloca(&port_info);

    snd_seq_client_info_set_client(client_info, -1);

    while (!snd_seq_query_next_client(d->seq, client_info)) {
        if (!strstr(
            snd_seq_client_info_get_name(client_info), "Oxygen 61")) {
            continue;
        }

        snd_seq_port_info_set_client(port_info,
            snd_seq_client_info_get_client(client_info));
        snd_seq_port_info_set_port(port_info, -1);

        while (!snd_seq_query_next_port(d->seq, port_info)) {
            caps = snd_seq_port_info_get_capability(port_info);

            if (!(caps & SND_SEQ_PORT_CAP_SUBS_READ)) {
                continue;
            }

            retval = snd_seq_connect_from(d->seq, d->seq_port,
                snd_seq_client_info_get_client(client_info),
                snd_seq_port_info_get_port(port_info));

            if (retval) {
                printf("Failed to solicit connection: %s\n",
                    snd_strerror(retval));
            } else {
                printf("Successfully connected a device: %s::%s\n",
                    snd_seq_client_info_get_name(client_info),
                    snd_seq_port_info_get_name(port_info));
                d->connected++;
                return;
            }
        }
   }
}

void setup_sequencer(struct dioxide *d) {
    int retval;

    retval = snd_seq_open(&d->seq, "default",
        SND_SEQ_OPEN_INPUT, SND_SEQ_NONBLOCK);

    if (retval) {
        printf("Couldn't open sequencer: %s\n", snd_strerror(retval));
        exit(retval);
    }

    snd_seq_set_client_name(d->seq, "Dioxide");

    retval = snd_seq_create_simple_port(d->seq, "Dioxide",
        SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_SUBS_WRITE,
        SND_SEQ_PORT_TYPE_MIDI_GENERIC);

    if (retval < 0) {
        printf("Couldn't open port: %s\n", snd_strerror(retval));
        exit(retval);
    } else {
        d->seq_port = retval;
    }
}
