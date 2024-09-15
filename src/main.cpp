#include <Arduino.h>
#include "wifi_manager/wifi_manager.h"
#include "pins/pins.h"

void setup() {
    Serial.begin(115200);

    // Настраиваем пин кнопки BOOT
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_FLASH_PIN, OUTPUT);

    // Инициализация Wi-Fi через WiFiManager
    WiFiManagerSetup();
}

void loop() {
    // Проверка состояния Wi-Fi и кнопки BOOT
    WiFiManagerLoop();
}
