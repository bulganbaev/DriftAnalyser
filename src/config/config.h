#ifndef CONFIG_H
#define CONFIG_H

// Настройки Wi-Fi
#define AP_SSID "ESP32_AP"      // Имя точки доступа
#define AP_PASSWORD "password"  // Пароль для точки доступа
#define NUM_STRIPS 6
const int numLEDsPerStrip[NUM_STRIPS] = {94, 94, 94, 94, 94, 94};
const int numLEDsPerSide[4] = {150, 300, 150, 300}; //front left bottom right

// Telegram bot settings
#define BOT_TOKEN "7291867516:AAFophQTJidUnWbfExvkH7Ev9W8ijuDOOmw"  // Replace with your Telegram bot token


#endif
