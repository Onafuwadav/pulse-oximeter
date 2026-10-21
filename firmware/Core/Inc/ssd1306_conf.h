/* Settings for the stm32-ssd1306 library (github.com/afiskon/stm32-ssd1306) */
#ifndef __SSD1306_CONF_H__
#define __SSD1306_CONF_H__

#define STM32L4
#define SSD1306_USE_I2C
#define SSD1306_I2C_PORT        hi2c1
#define SSD1306_I2C_ADDR        (0x3C << 1)

#define SSD1306_INCLUDE_FONT_11x18

#endif
