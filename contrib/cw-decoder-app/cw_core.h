/* CW (Morse) decoder core — integer/float DSP, no SDK or libc dependency beyond cosf.
 *
 * Feed it demodulated RX audio (mono int16) and it calls on_char() with decoded ASCII.
 * The radio hands apps 12 kHz audio (hb/audio.h); in CW mode that audio is the beat note
 * at the configured CW PITCH. The decoder: a Goertzel tone detector at the pitch, an
 * adaptive on/off threshold, and self-timing Morse element/gap classification.
 *
 * Portable: host_test.c builds this with the standard library to verify the algorithm.
 */
#ifndef CW_CORE_H
#define CW_CORE_H

#include <stdint.h>
#include <stdbool.h>

typedef void (*cw_char_fn)(void *ctx, char c);

typedef struct {
    /* Goertzel */
    float coeff, s1, s2, scale;
    int   frame_n, acc;
    float frame_ms;

    /* adaptive level / threshold (decaying min & max envelope) */
    float mag, mn, mx, thr;
    bool  tone, prev_tone;

    /* element timing */
    int   on_frames, off_frames;
    float dit_ms;
    bool  char_done, word_done;

    /* current symbol being built */
    char  sym[10];
    int   symlen;

    /* read-only, for a UI */
    float ui_mag, ui_thr;
    bool  ui_tone;
    int   ui_wpm, pitch_hz;
} cw_rx;

void cw_init(cw_rx *r, int sample_rate, int pitch_hz);
void cw_set_pitch(cw_rx *r, int sample_rate, int pitch_hz);

/* Process n samples; on_char(ctx, c) is called for each decoded character (c may be ' '). */
void cw_process(cw_rx *r, const int16_t *x, int n, cw_char_fn on_char, void *ctx);

#endif
