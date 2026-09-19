/* Experimental coefficient parity primitive for native H.264/H.265 hooks.
 * Only enabled in an isolated process with AGY_VIDEO_CONFIG. */
#ifndef AGY_VIDEO_WATERMARK_H
#define AGY_VIDEO_WATERMARK_H
#include <stdio.h>
#include <stdlib.h>
#define AGY_VIDEO_BITS 280
static int agy_video_ready = -1;
static unsigned char agy_video_bits[AGY_VIDEO_BITS];
static unsigned short agy_video_map[AGY_VIDEO_BITS];
static int agy_video_init(void)
{
    unsigned char data[4+AGY_VIDEO_BITS*3];
    const char *path;
    FILE *f;
    int i;
    if (agy_video_ready >= 0) return agy_video_ready;
    agy_video_ready = 0;
    path = getenv("AGY_VIDEO_CONFIG");
    if (!path || !(f = fopen(path, "rb"))) return 0;
    if (fread(data, 1, sizeof(data), f) != sizeof(data)) { fclose(f); return 0; }
    fclose(f);
    if (data[0]!='V' || data[1]!='W' || data[2]!='M' || data[3]!='1') return 0;
    for (i=0;i<AGY_VIDEO_BITS;i++) {
        agy_video_bits[i]=data[4+i];
        agy_video_map[i]=data[4+AGY_VIDEO_BITS+2*i] | (data[5+AGY_VIDEO_BITS+2*i]<<8);
        if (agy_video_bits[i]>1 || agy_video_map[i]>=AGY_VIDEO_BITS) return 0;
    }
    agy_video_ready=1;
    return 1;
}
static int agy_video_enabled(void)
{
    return getenv("AGY_VIDEO_EMBED") && agy_video_init();
}
static int agy_video_embed(int value, long long index)
{
    int bit, magnitude, sign;
    if (!agy_video_enabled() || index<0) return value;
    bit=agy_video_bits[agy_video_map[index%AGY_VIDEO_BITS]];
    magnitude=abs(value);
    sign=value<0 ? -1 : 1;
    if ((magnitude&1)!=bit) magnitude++;
    if (!magnitude) magnitude=2;
    if (magnitude>32767) magnitude-=2;
    return sign*magnitude;
}
static unsigned long long agy_video_counts[AGY_VIDEO_BITS][2];
static int agy_video_registered;
static void agy_video_flush(void)
{
    const char *path=getenv("AGY_VIDEO_EXTRACT");
    FILE *f;
    int i;
    if (!path || !(f=fopen(path,"ab"))) return;
    for (i=0;i<AGY_VIDEO_BITS;i++)
        fprintf(f,"%d %llu %llu\n",i,agy_video_counts[i][0],agy_video_counts[i][1]);
    fclose(f);
}
static void agy_video_extract(long long index, unsigned int magnitude)
{
    if (!getenv("AGY_VIDEO_EXTRACT") || !agy_video_init() || index<0) return;
    if (!agy_video_registered) {
        atexit(agy_video_flush);
        agy_video_registered=1;
    }
    agy_video_counts[index%AGY_VIDEO_BITS][magnitude&1]++;
}
#endif
