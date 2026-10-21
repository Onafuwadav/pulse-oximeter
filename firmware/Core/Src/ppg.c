/* Heart rate and SpO2 from the sampled PPG.
 * Reconstruction written in 2026 - the original firmware was lost. */
#include "ppg.h"
#include "arm_math.h"

static arm_rfft_fast_instance_f32 fft;
static float32_t fft_in[FFT_SIZE];
static float32_t fft_out[FFT_SIZE];
static float32_t mag[FFT_SIZE / 2];

void ppg_init(void)
{
  arm_rfft_fast_init_f32(&fft, FFT_SIZE);
}

/* Heart rate = biggest FFT peak between 40 and 200 bpm. */
float ppg_heart_rate(const float *ac, uint32_t n)
{
  float32_t mean;
  arm_mean_f32(ac, n, &mean);

  for (uint32_t i = 0; i < FFT_SIZE; i++)
    fft_in[i] = (i < n) ? ac[i] - mean : 0.0f;    /* remove DC, zero-pad */

  arm_rfft_fast_f32(&fft, fft_in, fft_out, 0);
  arm_cmplx_mag_f32(fft_out, mag, FFT_SIZE / 2);

  uint32_t lo = (uint32_t)((40.0f / 60.0f) * FFT_SIZE / FS) + 1;
  uint32_t hi = (uint32_t)((200.0f / 60.0f) * FFT_SIZE / FS);
  float32_t peak;
  uint32_t idx;
  arm_max_f32(&mag[lo], hi - lo + 1, &peak, &idx);
  uint32_t k = lo + idx;

  /* bins are 4.7 bpm apart, so fit a parabola through the peak and its neighbours */
  float32_t a = mag[k - 1], b = mag[k], c = mag[k + 1];
  float32_t offset = 0.5f * (a - c) / (a - 2.0f * b + c);

  return ((float32_t)k + offset) * FS / FFT_SIZE * 60.0f;
}

/* SpO2 = 110 - 25R, R = (AC_red / DC_red) / (AC_IR / DC_IR) */
float ppg_spo2(const float *ac_red, const float *dc_red,
               const float *ac_ir,  const float *dc_ir, uint32_t n)
{
  float32_t max, min, dc_r, dc_i;
  uint32_t idx;

  arm_max_f32(ac_red, n, &max, &idx);
  arm_min_f32(ac_red, n, &min, &idx);
  float32_t ac_r = max - min;

  arm_max_f32(ac_ir, n, &max, &idx);
  arm_min_f32(ac_ir, n, &min, &idx);
  float32_t ac_i = max - min;

  arm_mean_f32(dc_red, n, &dc_r);
  arm_mean_f32(dc_ir, n, &dc_i);

  if (ac_i <= 0.0f || dc_r <= 0.0f || dc_i <= 0.0f)
    return 0.0f;

  /* the 2nd-stage gain is the same for both colours, so it cancels in R */
  float32_t R = (ac_r / dc_r) / (ac_i / dc_i);
  return 110.0f - 25.0f * R;
}
