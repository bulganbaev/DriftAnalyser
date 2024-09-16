#include <Arduino.h>
#include "wifi_manager/wifi_manager.h"
#include "pins/pins.h"
#include "led_control/led_control.h"
#include "gps_controller/gps_controller.h"

void setup() {
    Serial.begin(115200);

    // Настраиваем пин кнопки BOOT
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_FLASH_PIN, OUTPUT);

    // Инициализация Wi-Fi через WiFiManager
    WiFiManagerSetup();

    initializeLEDStrips();

     // Initialize the GPS module
    initializeGPS();

}

void loop() {
    // Проверка состояния Wi-Fi и кнопки BOOT
    WiFiManagerLoop();
    runAnimations();
    // Show the results on the LED strips
    FastLED.show();
    // Adjust delay for animation speed control
    delay(50);
}
