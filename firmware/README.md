# firmware/

STM32 firmware for the pulse oximeter (STM32CubeIDE).

> **Reconstruction written in 2026.** The original firmware was lost. This follows the same design and compiles against the STM32L4 HAL, but it has not been run on hardware.

| File | Contents |
|---|---|
| `Core/Src/main.c` | Peripheral setup, ADC interrupt, main loop, OLED screen, RS-485 byte |
| `Core/Src/ppg.c` | Heart rate (CMSIS-DSP FFT) and SpO₂ (ratio of ratios) |
| `Core/Inc/ssd1306_conf.h` | Settings for the OLED library |

| Peripheral | Setting | Pin |
|---|---|---|
| TIM1 | PWM CH1 (red) and CH2 (IR), PSC 799, ARR 1249 → 80 Hz; TRGO = update | PA8, PA9 |
| TIM2 | Slave reset from ITR0 (TIM1), PSC 799, ARR 624; TRGO = OC1REF, CH1 pulse 469 | internal |
| ADC1 | IN1, external trigger TIM2 TRGO, rising edge | PC0 (DC) |
| ADC2 | IN2, external trigger TIM2 TRGO, rising edge; ADC1/ADC2 interrupt enabled | PC1 (AC) |
| I2C1 | Standard mode, 100 kHz | PB8, PB9 |
| USART1 | 57 600 8N1 | PB6 (to RS-485 transceiver, DE tied high) |
| USART2 | 115 200 8N1 | PA2, PA3 (ST-LINK virtual COM port) |

**How it works:** TIM1 alternates the red and IR LEDs at 80 Hz. TIM2 is reset by TIM1 every period and triggers both ADCs 75 % of the way into each LED's on-time, after the amplifier has settled. In the ADC interrupt, TIM1's counter shows which LED was on, so each sample goes into the red or IR buffer. Every 512 samples per colour (6.4 s), the main loop:
- computes heart rate from the biggest FFT peak between 40 and 200 bpm;
- computes SpO₂ from the AC peak-to-peak and DC mean of each colour;
- updates the OLED;
- sends SpO₂ to the display board as two BCD digits;
- prints both values for a serial plotter.

**Known limitation:** measuring AC as plain max − min reads SpO₂ low when breathing makes the baseline drift. Band-pass filtering the AC signal first would fix it.
