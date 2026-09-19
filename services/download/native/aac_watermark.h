/* Experimental AAC-LC MDCT hooks for the pinned FFmpeg 7.1 build.
 * Per-process configuration; invoke one isolated CLI process per operation.
 * Hooks are inactive unless AGY_AAC_CONFIG is set. No keys are passed to C.
 */
#ifndef AGY_AAC_WATERMARK_H
#define AGY_AAC_WATERMARK_H
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define AGY_AAC_BITS 280
#ifndef AGY_AAC_STEP
#define AGY_AAC_STEP 0.96
#endif
#ifndef AGY_CONFIG_ENV
#define AGY_CONFIG_ENV "AGY_AAC_CONFIG"
#define AGY_EMBED_ENV "AGY_AAC_EMBED"
#define AGY_EXTRACT_ENV "AGY_AAC_EXTRACT"
#define AGY_COEFFICIENTS 1024
#endif
static int agy_aac_ready = -1;
static unsigned char agy_aac_bits[AGY_AAC_BITS];
static unsigned short agy_aac_bins[64];

static int agy_aac_init(void)
{
    unsigned char buf[4 + AGY_AAC_BITS + 128];
    const char *path;
    FILE *f;
    int i;
    if (agy_aac_ready >= 0) return agy_aac_ready;
    agy_aac_ready = 0;
    path = getenv(AGY_CONFIG_ENV);
    if (!path || !(f = fopen(path, "rb"))) return 0;
    if (fread(buf, 1, sizeof(buf), f) != sizeof(buf)) { fclose(f); return 0; }
    fclose(f);
    if (buf[0] != 'A' || buf[1] != 'W' || buf[2] != 'M' || buf[3] != '1') return 0;
    for (i = 0; i < AGY_AAC_BITS; i++) {
        if (buf[4+i] > 1) return 0;
        agy_aac_bits[i] = buf[4+i];
    }
    for (i = 0; i < 64; i++) {
        agy_aac_bins[i] = buf[4+AGY_AAC_BITS+2*i] | (buf[5+AGY_AAC_BITS+2*i] << 8);
        if (agy_aac_bins[i] < 1 || agy_aac_bins[i] >= AGY_COEFFICIENTS) return 0;
    }
    agy_aac_ready = 1;
    return 1;
}

static double agy_aac_energy(const float *coeff, int offset)
{
    double sum = 0;
    int j;
    for (j = 0; j < 4; j++) {
        double v = coeff[agy_aac_bins[offset+j]];
        sum += v*v;
    }
    return sqrt(sum);
}

static void agy_aac_embed(float *coeff, long long frame, int short_window)
{
    int lane, j;
    if (!getenv(AGY_EMBED_ENV) || !agy_aac_init() || short_window || frame < 0) return;
    for (lane = 0; lane < 8; lane++) {
        double a = agy_aac_energy(coeff, lane*8);
        double b = agy_aac_energy(coeff, lane*8+4);
        double ratio, target, desired, gain;
        if (a < 1e-12 || b < 1e-12) continue;
        ratio = log(a/b);
        target = agy_aac_bits[(frame*8+lane) % AGY_AAC_BITS] * AGY_AAC_STEP / 2;
        desired = AGY_AAC_STEP * nearbyint((ratio-target)/AGY_AAC_STEP) + target;
        gain = exp((desired-ratio)/2);
        for (j = 0; j < 4; j++) {
            coeff[agy_aac_bins[lane*8+j]] *= gain;
            coeff[agy_aac_bins[lane*8+4+j]] /= gain;
        }
    }
}

static void agy_aac_extract(const float *coeff, long long frame, int short_window)
{
    const char *path = getenv(AGY_EXTRACT_ENV);
    FILE *f;
    int lane;
    if (!path || !agy_aac_init() || !(f = fopen(path, "ab"))) return;
    fprintf(f, "%lld", frame);
    for (lane = 0; lane < 8; lane++) {
        double a = agy_aac_energy(coeff, lane*8);
        double b = agy_aac_energy(coeff, lane*8+4);
        double ratio = (!short_window && a > 1e-12 && b > 1e-12) ? log(a/b) : NAN;
        fprintf(f, " %.9g", ratio);
    }
    fprintf(f, "\n");
    fclose(f);
}
#endif
