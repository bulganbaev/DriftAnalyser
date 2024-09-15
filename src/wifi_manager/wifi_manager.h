#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

// Объявление функций для управления Wi-Fi и кнопкой
void WiFiManagerSetup();       // Функция для инициализации Wi-Fi Manager
void WiFiManagerLoop();        // Основной цикл для работы Wi-Fi Manager
void startWiFiConfigPortal();  // Функция для запуска конфигурационного портала
void stopWiFiConfigPortal();   // Функция для остановки конфигурационного портала
void checkBootButton();        // Функция для обработки кнопки BOOT

#endif
