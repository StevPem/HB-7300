#include "cw_core.h"

/* cosf: use the SDK's hb_cosf on the radio, libm on the host (host_test defines CW_HOST). */
#ifdef CW_HOST
#include <math.h>
#define COSF cosf
#else
#include "hb/math.h"
#define COSF hb_cosf
#endif
#include <string.h>

#define PI 3.14159265358979f

/* Morse table: pattern (dots/dashes) -> character. */
static const struct { const char *code; char ch; } MORSE[] = {
    {".-",'A'},{"-...",'B'},{"-.-.",'C'},{"-..",'D'},{".",'E'},{"..-.",'F'},
    {"--.",'G'},{"....",'H'},{"..",'I'},{".---",'J'},{"-.-",'K'},{".-..",'L'},
    {"--",'M'},{"-.",'N'},{"---",'O'},{".--.",'P'},{"--.-",'Q'},{".-.",'R'},
    {"...",'S'},{"-",'T'},{"..-",'U'},{"...-",'V'},{".--",'W'},{"-..-",'X'},
    {"-.--",'Y'},{"--..",'Z'},
    {"-----",'0'},{".----",'1'},{"..---",'2'},{"...--",'3'},{"....-",'4'},
    {".....",'5'},{"-....",'6'},{"--...",'7'},{"---..",'8'},{"----.",'9'},
    {".-.-.-",'.'},{"--..--",','},{"..--..",'?'},{"-..-.",'/'},{"-...-",'='},
    {"-.-.--",'!'},{".-.-.",'+'},{"---...",':'},{"-....-",'-'},{".--.-.",'@'},
    {"-.--.",'('},{"-.--.-",')'},{".-...",'&'},{".----.",'\''},{".-..-.",'"'},
    {0,0}
};

static char decode_sym(const char *s)
{
    if (!s[0]) return 0;
    for (int i = 0; MORSE[i].code; i++)
        if (!strcmp(MORSE[i].code, s)) return MORSE[i].ch;
    return '#';                 /* unresolved pattern */
}

void cw_set_pitch(cw_rx *r, int sample_rate, int pitch_hz)
{
    float w = 2.0f * PI * (float)pitch_hz / (float)sample_rate;
    r->coeff = 2.0f * COSF(w);
    r->pitch_hz = pitch_hz;
}

void cw_init(cw_rx *r, int sample_rate, int pitch_hz)
{
    memset(r, 0, sizeof *r);
    r->scale    = 1.0f / 32768.0f;
    r->frame_n  = 64;                                   /* 5.33 ms @ 12 kHz */
    r->frame_ms = 1000.0f * (float)r->frame_n / (float)sample_rate;
    r->dit_ms   = 60.0f;                                /* ~20 WPM, adapts */
    r->mn = 0.0f; r->mx = 0.01f; r->thr = 0.005f;
    cw_set_pitch(r, sample_rate, pitch_hz);
}

static void emit_char(cw_rx *r, cw_char_fn on_char, void *ctx)
{
    r->sym[r->symlen] = 0;
    char c = decode_sym(r->sym);
    r->symlen = 0;
    if (c && on_char) on_char(ctx, c);
}

static void on_frame(cw_rx *r, float mag, cw_char_fn on_char, void *ctx)
{
    r->mag = mag;

    /* decaying envelope: fast toward a new extreme, slow relax back */
    if (mag > r->mx) r->mx = mag; else r->mx += (mag - r->mx) * 0.002f;
    if (mag < r->mn) r->mn = mag; else r->mn += (mag - r->mn) * 0.002f;
    float span = r->mx - r->mn;
    r->thr = r->mn + span * 0.5f;

    /* tone decision with hysteresis; ignore when there is essentially no signal */
    if (span < 0.0008f) {
        r->tone = false;
    } else if (!r->tone && mag > r->thr + span * 0.10f) {
        r->tone = true;
    } else if (r->tone && mag < r->thr - span * 0.10f) {
        r->tone = false;
    }
    r->ui_mag = mag; r->ui_thr = r->thr; r->ui_tone = r->tone;

    if (r->tone && !r->prev_tone) {             /* space ended, mark begins */
        r->off_frames = 0;
        r->char_done = r->word_done = false;
    }
    if (!r->tone && r->prev_tone) {             /* mark ended */
        float dur = r->on_frames * r->frame_ms;
        r->on_frames = 0;
        if (dur < 1.8f * r->dit_ms) {           /* dit */
            if (r->symlen < 9) r->sym[r->symlen++] = '.';
            r->dit_ms += (dur - r->dit_ms) * 0.20f;
        } else {                                /* dah */
            if (r->symlen < 9) r->sym[r->symlen++] = '-';
            r->dit_ms += (dur / 3.0f - r->dit_ms) * 0.10f;
        }
        if (r->dit_ms < 20.0f) r->dit_ms = 20.0f;      /* clamp 7.5..60 WPM */
        if (r->dit_ms > 160.0f) r->dit_ms = 160.0f;
        r->ui_wpm = (int)(1200.0f / r->dit_ms + 0.5f);
    }

    if (r->tone) { r->on_frames++; }
    else {
        r->off_frames++;
        float off = r->off_frames * r->frame_ms;
        if (r->symlen > 0 && !r->char_done && off >= 2.2f * r->dit_ms) {
            emit_char(r, on_char, ctx);          /* letter gap -> decode */
            r->char_done = true;
        }
        if (r->char_done && !r->word_done && off >= 5.5f * r->dit_ms) {
            if (on_char) on_char(ctx, ' ');      /* word gap */
            r->word_done = true;
        }
    }
    r->prev_tone = r->tone;
}

void cw_process(cw_rx *r, const int16_t *x, int n, cw_char_fn on_char, void *ctx)
{
    for (int i = 0; i < n; i++) {
        float y = (float)x[i] * r->scale;
        float s0 = y + r->coeff * r->s1 - r->s2;
        r->s2 = r->s1; r->s1 = s0;
        if (++r->acc >= r->frame_n) {
            float mag = r->s1 * r->s1 + r->s2 * r->s2 - r->coeff * r->s1 * r->s2;
            mag = mag > 0.0f ? mag : 0.0f;
            /* magnitude ~ sqrt(power)/N so levels are comparable across frame sizes */
            float amp = 0.0f, g = mag;
            /* cheap sqrt (Newton, 3 iters) to avoid libm on the radio */
            if (g > 0.0f) { amp = g; for (int k = 0; k < 4; k++) amp = 0.5f * (amp + g / amp); }
            on_frame(r, amp / (float)r->frame_n, on_char, ctx);
            r->s1 = r->s2 = 0.0f; r->acc = 0;
        }
    }
}
