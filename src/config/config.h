#ifndef CONFIG_H
#define CONFIG_H

// Настройки Wi-Fi
#define AP_SSID "ZverCustomLed"      // Имя точки доступа
#define AP_PASSWORD "qwerty12345"  // Пароль для точки доступа
#define NUM_STRIPS 6

// Default STA network, used until changed in the hub.
// Put real values into src/config/secrets.h (gitignored), see secrets.example.h
#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef DEFAULT_NETWORKS
#define DEFAULT_NETWORKS { {"", ""} }
#endif


#endif
