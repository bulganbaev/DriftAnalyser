#ifndef PINS_H
#define PINS_H

// DriftAnalyser PCB v2, see PCB/v2/README.md "Карта GPIO"
#define BOOT_BUTTON_PIN 0

#define VBAT_SENSE_PIN 1   // ADC1, divider 47k/10k
#define LED_ISENSE_PIN 2   // ADC1, BTS7002 IS into 470R

// LED strip data, through 74HCT245
#define LED_PIN_1 4
#define LED_PIN_2 5
#define LED_PIN_3 6
#define LED_PIN_4 7
#define LED_PIN_5 15
#define LED_PIN_6 16

#define LED_PWR_EN_PIN 10  // BTS7002 IN, 10k pull-down: strips are off until set
#define STATUS_LED_PIN 11  // high = on

// LSM6DS3TR-C, I2C shared with the EXT connector
#define IMU_SDA_PIN 8
#define IMU_SCL_PIN 9
#define IMU_INT1_PIN 17

// TJA1027 K-line on UART1, SLP_N tied high
#define K_RX_PIN 12
#define K_TX_PIN 13

// TJA1051, S pin has a 10k pull-up (silent) until driven low
#define CAN_RX_PIN 21
#define CAN_TX_PIN 18
#define CAN_STB_PIN 14

#endif
