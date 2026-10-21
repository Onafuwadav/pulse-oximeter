#ifndef PPG_H
#define PPG_H

#include <stdint.h>

#define FS          80.0f   /* samples per second per LED (one per PWM period) */
#define FFT_SIZE    1024    /* window is zero-padded up to this */

void  ppg_init(void);
float ppg_heart_rate(const float *ac, uint32_t n);
float ppg_spo2(const float *ac_red, const float *dc_red,
               const float *ac_ir,  const float *dc_ir, uint32_t n);

#endif
