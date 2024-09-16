#include "wifi_manager.h"
#include <WiFiManager.h>
#include <WiFi.h>
#include "pins/pins.h"
#include "config/config.h"

// Переменные для антидребезга и удержания кнопки
unsigned long lastDebounceTime = 0;
const long debounceDelay = 50;  // 50 мс для антидребезга
bool isButtonHeld = false;
unsigned long buttonPressTime = 0;
const long buttonHoldTime = 3000;  // Удержание кнопки 3 секунды
const long buttonShortPressTime = 500;  // Короткое нажатие

bool lastButtonState = HIGH;  // Последнее состояние кнопки
WiFiManager wm;               // Создаем объект WiFiManager
bool wifiConnected = false;
bool apModeActive = false;    // Переменная для отслеживания, активен ли AP

// Переменные для таймаута подключения к Wi-Fi
unsigned long wifiConnectStartTime = 0;
const long wifiConnectTimeout = 10000;  // Таймаут на подключение к сети 10 секунд

// Для асинхронной индикации
unsigned long lastBlinkTime = 0;
const long blinkInterval = 500;  // Интервал мигания 500 мс
bool ledState = LOW;

void WiFiManagerSetup() {
    wifiConnectStartTime = millis();  // Запоминаем время начала попытки подключения
    wifiConnected = wm.autoConnect(AP_SSID, AP_PASSWORD);  // Попытка подключения

    if (!wifiConnected) {
        Serial.println("Failed to connect to saved network within timeout, starting AP mode...");
        startWiFiConfigPortal();
    } else {
        Serial.println("WiFi connected successfully.");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        stopWiFiConfigPortal();  // Выключаем точку доступа, если Wi-Fi подключен
    }
}

// Функция для запуска конфигурационного портала Wi-Fi
void startWiFiConfigPortal() {
    Serial.println("Starting Wi-Fi Config Portal...");
    wm.startConfigPortal(AP_SSID, AP_PASSWORD);
    apModeActive = true;  // Устанавливаем флаг, что точка доступа активна
}

// Функция для остановки конфигурационного портала и точки доступа
void stopWiFiConfigPortal() {
    if (apModeActive) {
        Serial.println("Stopping Wi-Fi Config Portal...");
        wm.stopWebPortal();  // Останавливаем веб-портал
        WiFi.softAPdisconnect(true);  // Отключаем точку доступа
        apModeActive = false;   // Сбрасываем флаг
    }
}

// Функция для индикации состояния Wi-Fi
void indicateWiFiStatus() {
    if (WiFi.status() != WL_CONNECTED) {
        // Асинхронная индикация - мигание светодиода, если сеть не подключена
        if (millis() - lastBlinkTime > blinkInterval) {
            ledState = !ledState;  // Меняем состояние светодиода
            digitalWrite(LED_FLASH_PIN, ledState);  // Обновляем состояние светодиода
            lastBlinkTime = millis();  // Обновляем таймер
        }
    } else {
        // Если сеть подключена, светодиод включен постоянно
        digitalWrite(LED_FLASH_PIN, HIGH);
    }
}

// Функция для забытия всех сетей и сброса настроек
void forgetWiFi() {
    Serial.println("Forgetting all Wi-Fi connections...");
    wm.resetSettings();  // Сбрасываем все сохраненные сети
}

// Функция для обработки кнопки BOOT с различием между коротким и длинным нажатием
void checkBootButton() {
    int reading = digitalRead(BOOT_BUTTON_PIN);

    // Если состояние кнопки изменилось, сбрасываем таймер для антидребезга
    if (reading != lastButtonState) {
        lastDebounceTime = millis();  // Обновляем таймер
    }

    // Проверка с антидребезгом
    if ((millis() - lastDebounceTime) > debounceDelay) {
        // Если кнопка нажата (LOW) и еще не была обработана как удержание
        if (reading == LOW && !isButtonHeld) {
            buttonPressTime = millis();  // Начало удержания кнопки
            isButtonHeld = true;
        }

        // Сброс состояния кнопки при отпускании
        if (reading == HIGH && isButtonHeld) {
            // Если кнопка была удержана более 3 секунд, это длинное нажатие
            if (millis() - buttonPressTime >= buttonHoldTime) {
                Serial.println("BOOT button held, forgetting Wi-Fi and starting AP mode...");
                forgetWiFi();  // Забудем все сохраненные сети
                startWiFiConfigPortal();  // Запустим точку доступа
            } 
            // Если кнопка была удержана менее 3 секунд, это короткое нажатие
            else if (millis() - buttonPressTime >= buttonShortPressTime) {
                Serial.println("Short press detected, doing some action...");
                // Действие для короткого нажатия
            }

            // Сбрасываем состояние удержания кнопки
            isButtonHeld = false;
        }
    }

    lastButtonState = reading;  // Обновляем последнее состояние кнопки
}

void WiFiManagerLoop() {
    // Проверяем состояние Wi-Fi и индикацию
    indicateWiFiStatus();

    // Проверяем кнопку BOOT
    checkBootButton();

    // Проверка таймаута подключения к Wi-Fi
    if (!wifiConnected && (millis() - wifiConnectStartTime > wifiConnectTimeout)) {
        Serial.println("Wi-Fi connection timeout reached, starting AP mode...");
        startWiFiConfigPortal();  // Если таймаут истек, запускаем точку доступа
        wifiConnected = true;  // Сбрасываем переменную для предотвращения повторных запусков
    }
}
