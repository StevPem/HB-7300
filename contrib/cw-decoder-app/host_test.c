/* Host test for cw_core: synthesize keyed CW audio, decode it, print the result.
 * Build:  cc -DCW_HOST -O2 -o cw_test host_test.c cw_core.c -lm
 */
#include "cw_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define FS    12000
#define PITCH 600

static const struct { char ch; const char *code; } T[] = {
    {'A',".-"},{'B',"-..."},{'C',"-.-."},{'D',"-.."},{'E',"."},{'F',"..-."},
    {'G',"--."},{'H',"...."},{'I',".."},{'J',".---"},{'K',"-.-"},{'L',".-.."},
    {'M',"--"},{'N',"-."},{'O',"---"},{'P',".--."},{'Q',"--.-"},{'R',".-."},
    {'S',"..."},{'T',"-"},{'U',"..-"},{'V',"...-"},{'W',".--"},{'X',"-..-"},
    {'Y',"-.--"},{'Z',"--.."},{'0',"-----"},{'1',".----"},{'2',"..---"},
    {'3',"...--"},{'4',"....-"},{'5',"....."},{'6',"-...."},{'7',"--..."},
    {'8',"---.."},{'9',"----."},{'/',"-..-."},{'=',"-...-"},{0,0}
};
static const char *code_of(char c){for(int i=0;T[i].ch;i++)if(T[i].ch==c)return T[i].code;return 0;}

static char out[512]; static int outn;
static void on_char(void *ctx,char c){(void)ctx; if(outn<511) out[outn++]=c;}

int main(int argc, char **argv)
{
    int wpm = argc>1 ? atoi(argv[1]) : 22;
    double snr_db = argc>2 ? atof(argv[2]) : 100.0;
    const char *msg = argc>3 ? argv[3] : "CQ CQ DE HB9XYZ/P K";

    int dit = (int)(0.001 * (1200.0/wpm) * FS + 0.5);   /* samples per dit */
    double amp = 8000.0, nstd = amp / pow(10.0, snr_db/20.0);
    srand(1);

    /* build the audio: 0.3 s lead-in silence, then the message, then 1 s trailing */
    static int16_t buf[FS*30]; int N=0;
    for (int i=0;i<FS*3/10;i++) buf[N++]=0;
    double ph=0, dph=2*M_PI*PITCH/FS;
    void key(int samples,int on){
        for(int i=0;i<samples && N<FS*29;i++){
            double s = on ? amp*sin(ph) : 0.0;
            double no = nstd*((rand()/(double)RAND_MAX)-0.5)*3.4;
            int v=(int)(s+no); if(v>32767)v=32767; if(v<-32768)v=-32768;
            buf[N++]=(int16_t)v; ph+=dph; if(ph>2*M_PI)ph-=2*M_PI;
        }
    }
    for (const char *p=msg; *p; p++){
        if(*p==' '){ key(7*dit,0); continue; }
        const char *c=code_of(*p); if(!c) continue;
        for(const char *e=c; *e; e++){ key((*e=='.'?1:3)*dit,1); if(e[1]) key(dit,0); }
        key(3*dit,0);                 /* inter-character */
    }
    for(int i=0;i<FS;i++) buf[N++]=0;

    cw_rx rx; cw_init(&rx,FS,PITCH);
    /* feed in realistic chunks, like hb_audio_read */
    for(int i=0;i<N;i+=1024) cw_process(&rx,buf+i, (N-i<1024?N-i:1024), on_char, NULL);
    out[outn]=0;

    printf("WPM=%d SNR=%.0fdB  pitch=%d\n", wpm,snr_db,PITCH);
    printf("sent:    \"%s\"\n", msg);
    printf("decoded: \"%s\"   (est WPM=%d)\n", out, rx.ui_wpm);
    /* crude score: longest common run / ignore trailing space */
    return 0;
}
