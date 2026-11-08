/* CW decoder app for the IC-7300 homebrew SDK (jeskko/ic7300-homebrew, loader ABI v4).
 *
 * Tune a CW signal in CW/CW-R so it beats at your CW PITCH, start the app: it shows a tone
 * meter and scrolls decoded Morse as text. Tap PITCH to cycle 500/600/700/800 Hz. EXIT or the
 * on-screen X quits. DSP is cw_core.c (shared, host-tested). Audio: hb/audio.h (12 kHz RX).
 */
#include "hb/app.h"
#include "hb/audio.h"
#include "hb/gfx.h"
#include "hb/input.h"

#include "cw_core.h"
#include <stddef.h>

#define SCALE   2
#define ADV     (HB_FONT_ADVANCE * SCALE)       /* 12 px per char */
#define LH      (HB_FONT_H * SCALE + 4)         /* line height 18 px */
#define TOP     46                              /* text area starts below the meter/status */
#define COLS    ((HB_SCREEN_W - 8) / ADV)       /* ~39 */
#define ROWS    ((HB_SCREEN_H - TOP) / LH)      /* ~12 */
#define EXIT_S  40
#define EXIT_X  (HB_SCREEN_W - EXIT_S)

#define BG      HB_RGB(12, 14, 20)
#define FG      HB_RGB(210, 230, 210)
#define DIM     HB_RGB(120, 130, 140)
#define ACCENT  HB_RGB(90, 220, 120)
#define BAR     HB_RGB(60, 150, 90)
#define THRC    HB_RGB(230, 180, 60)

static char g_text[ROWS][COLS + 1];
static int  g_row, g_col;
static bool g_dirty = true;

static const int PITCHES[] = {500, 600, 700, 800};
static int g_pi = 1;                             /* start at 600 Hz */
static cw_rx g_rx;

static void text_newline(void)
{
    if (g_row < ROWS - 1) { g_row++; }
    else {                                       /* scroll up */
        for (int r = 0; r < ROWS - 1; r++)
            for (int c = 0; c <= COLS; c++) g_text[r][c] = g_text[r + 1][c];
        for (int c = 0; c <= COLS; c++) g_text[ROWS - 1][c] = 0;
    }
    g_col = 0;
}

static void on_char(void *ctx, char c)
{
    (void)ctx;
    if (g_col >= COLS) text_newline();
    g_text[g_row][g_col++] = c;
    g_text[g_row][g_col] = 0;
    g_dirty = true;
}

static void draw(hb_canvas *cv)
{
    hb_clear(cv, BG);

    /* tone meter: magnitude bar with a threshold tick */
    int mx = EXIT_X - 70;
    float span = g_rx.ui_mag > 0.02f ? g_rx.ui_mag * 1.2f : 0.02f;
    int w = (int)(g_rx.ui_mag / span * mx);
    if (w > mx) w = mx;
    if (w < 0) w = 0;
    hb_fill_rect(cv, 4, 6, mx, 16, HB_RGB(30, 34, 44));
    hb_fill_rect(cv, 4, 6, w, 16, g_rx.ui_tone ? ACCENT : BAR);
    int tx = (int)(g_rx.ui_thr / span * mx);
    if (tx >= 0 && tx < mx) hb_fill_rect(cv, 4 + tx, 4, 2, 20, THRC);

    /* status */
    char s[40]; int n = 0;
    const char *lbl = "CW  P=";
    for (const char *p = lbl; *p; p++) s[n++] = *p;
    int pz = g_rx.pitch_hz; s[n++]='0'+pz/100; s[n++]='0'+(pz/10)%10; s[n++]='0'+pz%10;
    s[n++]=' '; s[n++]='W'; s[n++]='P'; s[n++]='M'; s[n++]='=';
    int wpm = g_rx.ui_wpm; if (wpm>99) wpm=99;
    if (wpm>=10) s[n++]='0'+wpm/10;
    s[n++]='0'+wpm%10; s[n]=0;
    hb_text(cv, 4, 26, s, SCALE, DIM);

    /* PITCH touch hint + EXIT box */
    hb_text(cv, mx + 8, 8, "PTCH", 1, DIM);
    hb_fill_rect(cv, EXIT_X, 0, EXIT_S, EXIT_S, HB_RGB(60, 30, 30));
    hb_line(cv, EXIT_X+10, 10, EXIT_X+EXIT_S-10, EXIT_S-10, FG);
    hb_line(cv, EXIT_X+EXIT_S-10, 10, EXIT_X+10, EXIT_S-10, FG);

    /* decoded text */
    for (int r = 0; r < ROWS; r++)
        if (g_text[r][0]) hb_text(cv, 4, TOP + r * LH, g_text[r], SCALE, FG);
}

static bool touched_prev;

static void handle_input(bool *running)
{
    if (hb_key_down(HB_KEY_EXIT)) { *running = false; return; }
    hb_touch t; hb_touch_read(&t);
    if (t.down && !touched_prev) {
        if (t.x >= EXIT_X && t.y < EXIT_S) { *running = false; }
        else if (t.y < 40) {                 /* top strip: cycle pitch */
            g_pi = (g_pi + 1) % 4;
            cw_set_pitch(&g_rx, HB_AUDIO_RATE, PITCHES[g_pi]);
            g_dirty = true;
        }
    }
    touched_prev = t.down;
}

int main(void)
{
    if (!hb_gfx_open()) return 1;
    cw_init(&g_rx, HB_AUDIO_RATE, PITCHES[g_pi]);
    hb_audio_open();

    bool running = true;
    while (running) {
        int16_t buf[1024];
        int n;
        while ((n = hb_audio_read(buf, 1024)) > 0) {
            cw_process(&g_rx, buf, n, on_char, NULL);
            if (n < 1024) break;
        }
        handle_input(&running);
        draw(hb_gfx_canvas());               /* redraw every frame: the meter is live */
        hb_gfx_present();                    /* blocks until vsync; the radio keeps running */
    }

    hb_audio_close();
    hb_gfx_close();
    return 0;
}
