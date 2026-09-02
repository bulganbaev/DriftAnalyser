#include "system.h"
#include <LittleFS.h>
#include <esp_system.h>
#include "led_control/led_control.h"

static const char* LOG_PATH = "/log.txt";
static const char* LOG_OLD = "/log.old";
const size_t LOG_MAX = 24 * 1024;

String sysResetReason() {
    switch (esp_reset_reason()) {
        case ESP_RST_POWERON:   return F("power on");
        case ESP_RST_SW:        return F("software reset");
        case ESP_RST_PANIC:     return F("PANIC");
        case ESP_RST_INT_WDT:   return F("interrupt watchdog");
        case ESP_RST_TASK_WDT:  return F("task watchdog");
        case ESP_RST_WDT:       return F("watchdog");
        case ESP_RST_DEEPSLEEP: return F("deep sleep");
        case ESP_RST_BROWNOUT:  return F("BROWNOUT");
        case ESP_RST_SDIO:      return F("sdio");
        case ESP_RST_EXT:       return F("external");
        default:                return F("unknown");
    }
}

String sysUptime() {
    unsigned long s = millis() / 1000;
    char buf[32];
    snprintf(buf, sizeof(buf), "%lud %02lu:%02lu:%02lu", s / 86400, (s / 3600) % 24, (s / 60) % 60, s % 60);
    return String(buf);
}

#ifndef GIT_REV
#define GIT_REV "unknown"
#endif
String sysBuildInfo() {
    return String(F(GIT_REV " " __DATE__ " " __TIME__));
}

static void rotateIfNeeded() {
    if (!LittleFS.exists(LOG_PATH)) return;
    File f = LittleFS.open(LOG_PATH, "r");
    if (!f) return;
    size_t size = f.size();
    f.close();
    if (size < LOG_MAX) return;
    LittleFS.remove(LOG_OLD);
    LittleFS.rename(LOG_PATH, LOG_OLD);
}

void sysLog(const String& msg) {
    Serial.println(msg);
    bool wasPaused = ledsPaused();
    ledsPause();
    rotateIfNeeded();
    File f = LittleFS.open(LOG_PATH, "a");
    if (f) {
        f.print(sysUptime());
        f.print(' ');
        f.println(msg);
        f.close();
    }
    if (!wasPaused) ledsResume();
}

void sysBegin() {
    sysLog("--- boot, reset: " + sysResetReason() + ", build " + sysBuildInfo());
}

String sysLogTail(int maxBytes) {
    if (!LittleFS.exists(LOG_PATH)) return F("(no log)");
    File f = LittleFS.open(LOG_PATH, "r");
    if (!f) return F("(no log)");
    size_t size = f.size();
    if ((int)size > maxBytes) f.seek(size - maxBytes);
    String s;
    s.reserve(maxBytes + 1);
    while (f.available()) s += (char)f.read();
    f.close();
    if ((int)size > maxBytes) {
        int nl = s.indexOf('\n');
        if (nl >= 0) s = s.substring(nl + 1);
    }
    return s;
}

void sysClearLog() {
    ledsPause();
    LittleFS.remove(LOG_PATH);
    LittleFS.remove(LOG_OLD);
    ledsResume();
    sysLog(F("log cleared"));
}
