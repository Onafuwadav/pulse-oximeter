/* USER CODE BEGIN Header */
/*
 * EEEE2070 pulse oximeter - STM32 NUCLEO-L476RG
 *
 * Reconstruction written in 2026. The original firmware was lost; this
 * follows the same design but has not been run on hardware.
 *
 *  TIM1  80 Hz PWM: CH1 = red LED (first half), CH2 = IR LED (second half)
 *  TIM2  160 Hz, reset by TIM1 (slave, ITR0). TRGO = OC1REF, which rises 75 %
 *        of the way through each LED's on-time and triggers both ADCs
 *  ADC1  DC signal (after the TIA)            PC0
 *  ADC2  AC signal (after the 2nd stage)      PC1
 *  I2C1  SSD1306 OLED                         PB8 / PB9
 *  USART1 57600 8N1 to the RS-485 transceiver PB6 (DE tied high)
 *  USART2 115200 printf to the PC (ST-LINK virtual COM port)
 */
/* USER CODE END Header */
#include "main.h"

/* USER CODE BEGIN Includes */
#include <stdio.h>
#include "ppg.h"
#include "ssd1306.h"
#include "ssd1306_fonts.h"
/* USER CODE END Includes */

ADC_HandleTypeDef hadc1;
ADC_HandleTypeDef hadc2;
I2C_HandleTypeDef hi2c1;
TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart1;
UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
#define N_SAMPLES   512        /* 6.4 s per wavelength at 80 samples/s */
#define HALF_PERIOD 625        /* TIM1 ticks in one LED's on-time */

float dc_red[N_SAMPLES], dc_ir[N_SAMPLES];
float ac_red[N_SAMPLES], ac_ir[N_SAMPLES];
volatile uint32_t n_red = 0, n_ir = 0;
/* USER CODE END PV */

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ADC1_Init(void);
static void MX_ADC2_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM2_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_USART2_UART_Init(void);

/* USER CODE BEGIN 0 */
/* printf -> USART2 (from the module notes) */
int __io_putchar(int ch)
{
  HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
  return ch;
}

/* Both ADCs convert on the same trigger; ADC2's interrupt reads both.
 * TIM1's counter says which LED was on. */
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
  if (hadc != &hadc2)
    return;

  float dc = HAL_ADC_GetValue(&hadc1) * 3.3f / 4095.0f;
  float ac = HAL_ADC_GetValue(&hadc2) * 3.3f / 4095.0f;

  if (__HAL_TIM_GET_COUNTER(&htim1) < HALF_PERIOD) {
    if (n_red < N_SAMPLES) {
      dc_red[n_red] = dc;
      ac_red[n_red] = ac;
      n_red++;
    }
  } else {
    if (n_ir < N_SAMPLES) {
      dc_ir[n_ir] = dc;
      ac_ir[n_ir] = ac;
      n_ir++;
    }
  }
}

static void show_on_oled(int hr, int spo2)
{
  char line[16];

  ssd1306_Fill(Black);
  sprintf(line, "HR %3d bpm", hr);
  ssd1306_SetCursor(0, 0);
  ssd1306_WriteString(line, Font_11x18, White);
  sprintf(line, "SpO2 %2d%%", spo2);
  ssd1306_SetCursor(0, 20);
  ssd1306_WriteString(line, Font_11x18, White);

  /* pulse waveform: last 128 IR samples, scaled into rows 40-63
     (less light gets through on each beat, so low values are drawn at the top) */
  float min = ac_ir[N_SAMPLES - 128], max = min;
  for (int i = N_SAMPLES - 128; i < N_SAMPLES; i++) {
    if (ac_ir[i] < min) min = ac_ir[i];
    if (ac_ir[i] > max) max = ac_ir[i];
  }
  if (max > min) {
    for (int x = 0; x < 128; x++) {
      float v = ac_ir[N_SAMPLES - 128 + x];
      ssd1306_DrawPixel(x, 40 + (uint8_t)((v - min) / (max - min) * 23.0f), White);
    }
  }
  ssd1306_UpdateScreen();
}
/* USER CODE END 0 */

int main(void)
{
  HAL_Init();
  SystemClock_Config();

  MX_GPIO_Init();
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_I2C1_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();

  /* USER CODE BEGIN 2 */
  ssd1306_Init();
  ppg_init();

  HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
  HAL_ADC_Start(&hadc1);                       /* waits for the TIM2 trigger */
  HAL_ADC_Start_IT(&hadc2);

  HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);    /* ADC trigger (internal only) */
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);    /* red */
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);    /* IR */
  /* USER CODE END 2 */

  while (1)
  {
    /* USER CODE BEGIN 3 */
    if (n_red == N_SAMPLES && n_ir == N_SAMPLES) {
      float hr = ppg_heart_rate(ac_ir, N_SAMPLES);
      float spo2 = ppg_spo2(ac_red, dc_red, ac_ir, dc_ir, N_SAMPLES);

      int hr_i = (int)(hr + 0.5f);
      int spo2_i = (int)(spo2 + 0.5f);
      if (spo2_i > 99) spo2_i = 99;            /* two BCD digits can't show 100 */
      if (spo2_i < 0) spo2_i = 0;

      show_on_oled(hr_i, spo2_i);

      /* SpO2 to the display board as two BCD digits, e.g. 97 -> 0x97 */
      uint8_t bcd = ((spo2_i / 10) << 4) | (spo2_i % 10);
      HAL_UART_Transmit(&huart1, &bcd, 1, 10);

      printf("%d,%d\r\n", hr_i, spo2_i);       /* serial plotter */

      n_red = 0;                               /* start the next window */
      n_ir = 0;
    }
    /* USER CODE END 3 */
  }
}

/* 80 MHz from MSI (4 MHz) x 40 / 2 */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
    Error_Handler();

  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
  RCC_OscInitStruct.MSIState = RCC_MSI_ON;
  RCC_OscInitStruct.MSICalibrationValue = 0;
  RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_6;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_MSI;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 40;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV7;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    Error_Handler();

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                              | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
    Error_Handler();
}

static void adc_init(ADC_HandleTypeDef *hadc, ADC_TypeDef *instance, uint32_t channel)
{
  ADC_ChannelConfTypeDef sConfig = {0};

  hadc->Instance = instance;
  hadc->Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  hadc->Init.Resolution = ADC_RESOLUTION_12B;
  hadc->Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc->Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc->Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc->Init.ContinuousConvMode = DISABLE;
  hadc->Init.NbrOfConversion = 1;
  hadc->Init.ExternalTrigConv = ADC_EXTERNALTRIG_T2_TRGO;
  hadc->Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_RISING;
  hadc->Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
  if (HAL_ADC_Init(hadc) != HAL_OK)
    Error_Handler();

  sConfig.Channel = channel;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_47CYCLES_5;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  if (HAL_ADC_ConfigChannel(hadc, &sConfig) != HAL_OK)
    Error_Handler();
}

static void MX_ADC1_Init(void) { adc_init(&hadc1, ADC1, ADC_CHANNEL_1); }   /* PC0 */
static void MX_ADC2_Init(void) { adc_init(&hadc2, ADC2, ADC_CHANNEL_2); }   /* PC1 */

static void MX_I2C1_Init(void)
{
  hi2c1.Instance = I2C1;
  hi2c1.Init.Timing = 0x10909CEC;              /* 100 kHz at 80 MHz, from CubeMX */
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
    Error_Handler();
}

/* TIM1: 80 MHz / 800 = 100 kHz, / 1250 = 80 Hz. CH1 PWM1 and CH2 PWM2 at
   625 give two complementary halves: red, then IR. */
static void MX_TIM1_Init(void)
{
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  htim1.Instance = TIM1;
  htim1.Init.Prescaler = 799;
  htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim1.Init.Period = 1249;
  if (HAL_TIM_PWM_Init(&htim1) != HAL_OK)
    Error_Handler();

  sMasterConfig.MasterOutputTrigger = TIM_TRGO_UPDATE;     /* resets TIM2 */
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_ENABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim1, &sMasterConfig) != HAL_OK)
    Error_Handler();

  sConfigOC.Pulse = HALF_PERIOD;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
    Error_Handler();
  sConfigOC.OCMode = TIM_OCMODE_PWM2;
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
    Error_Handler();

  HAL_TIM_MspPostInit(&htim1);
}

/* TIM2: same 100 kHz clock, period 625 (one LED half). Slave of TIM1 so it
   stays in step; OC1REF goes high at 469 = 75 % through each half. */
static void MX_TIM2_Init(void)
{
  TIM_SlaveConfigTypeDef sSlaveConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 799;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = HALF_PERIOD - 1;
  if (HAL_TIM_PWM_Init(&htim2) != HAL_OK)
    Error_Handler();

  sSlaveConfig.SlaveMode = TIM_SLAVEMODE_RESET;
  sSlaveConfig.InputTrigger = TIM_TS_ITR0;                 /* ITR0 = TIM1 */
  if (HAL_TIM_SlaveConfigSynchro(&htim2, &sSlaveConfig) != HAL_OK)
    Error_Handler();

  sMasterConfig.MasterOutputTrigger = TIM_TRGO_OC1REF;     /* -> ADC trigger */
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
    Error_Handler();

  sConfigOC.OCMode = TIM_OCMODE_PWM2;
  sConfigOC.Pulse = 469;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
    Error_Handler();
}

static void uart_init(UART_HandleTypeDef *huart, USART_TypeDef *instance, uint32_t baud)
{
  huart->Instance = instance;
  huart->Init.BaudRate = baud;
  huart->Init.WordLength = UART_WORDLENGTH_8B;
  huart->Init.StopBits = UART_STOPBITS_1;
  huart->Init.Parity = UART_PARITY_NONE;
  huart->Init.Mode = UART_MODE_TX_RX;
  huart->Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart->Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(huart) != HAL_OK)
    Error_Handler();
}

static void MX_USART1_UART_Init(void) { uart_init(&huart1, USART1, 57600); }   /* RS-485 */
static void MX_USART2_UART_Init(void) { uart_init(&huart2, USART2, 115200); }  /* PC */

static void MX_GPIO_Init(void)
{
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
}

void Error_Handler(void)
{
  __disable_irq();
  while (1) {
  }
}
