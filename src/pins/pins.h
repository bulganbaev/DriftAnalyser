#ifndef PINS_H
#define PINS_H

// Определяем пин для кнопки BOOT
#define BOOT_BUTTON_PIN 0  // GPIO0 на ESP32-S3
#define LED_FLASH_PIN 4


// LED strip GPIO pins
#define LED_PIN_1 10
#define LED_PIN_2 21
#define LED_PIN_3 14
#define LED_PIN_4 40
#define LED_PIN_5 41
#define LED_PIN_6 42

// GPS module pins
#define GPS_RX_PIN 3  // RXD0 (UART0 default)
#define GPS_TX_PIN 1  // TXD0 (UART0 default)
#define GPS_PPS_PIN 48  // PPS (Pulse Per Second) on GPIO48

// spare 5V-level outputs (XH2.54 connectors), usable as LED data
#define SPST1_PIN 39
#define SPST2_PIN 38

// MPU-6050 I2C
#define IMU_SDA_PIN 8
#define IMU_SCL_PIN 9

//TJA1050 pins
#define CAN_RX_PIN 16
#define CAN_TX_PIN 35
#define CAN_STB_PIN 15

#endif
