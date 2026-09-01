#include "net.h"
#include <WiFi.h>
#include "config/config.h"
#include "system/system.h"

String wifiSsid, wifiPass;

static bool apOn = false;
static unsigned long staDownSince = 0;   // 0 = connected
static unsigned long lastStaAttempt = 0;
const unsigned long STA_TIMEOUT = 20000;  // no STA this long -> raise AP
const unsigned long STA_RETRY = 30000;    // retry STA while AP is on

static void startAP() {
    if (apOn) return;
    WiFi.mode(wifiSsid.length() ? WIFI_AP_STA : WIFI_AP);
    if (WiFi.softAP(AP_SSID, AP_PASSWORD)) {
        apOn = true;
        sysLog("AP started " + WiFi.softAPIP().toString());
    } else {
        Serial.println("Failed to start Access Point!");
    }
}

static void stopAP() {
    if (!apOn) return;
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    apOn = false;
    Serial.println("AP stopped");
}

static void startSTA() {
    Serial.print("Connecting to Wi-Fi: ");
    Serial.println(wifiSsid);
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
    lastStaAttempt = millis();
}

void netBegin() {
    WiFi.persistent(false);  // creds live in settings.dat, don't write NVS on every boot
    WiFi.setAutoReconnect(false);
    WiFi.setHostname("zvercustom");
    if (!wifiSsid.length()) {
        startAP();
        return;
    }
    WiFi.mode(WIFI_STA);
    staDownSince = millis();
    startSTA();
}

void netReconnect() {
    if (!wifiSsid.length()) {
        WiFi.disconnect();
        startAP();
        return;
    }
    if (!apOn) WiFi.mode(WIFI_STA);
    staDownSince = millis();
    startSTA();
}

void netTick() {
    if (!wifiSsid.length()) return;
    unsigned long now = millis();

    if (WiFi.status() == WL_CONNECTED) {
        if (staDownSince) {
            staDownSince = 0;
            sysLog("Wi-Fi connected " + WiFi.SSID() + " " + WiFi.localIP().toString());
        }
        stopAP();
        return;
    }

    if (!staDownSince) {
        staDownSince = now;
        sysLog(F("Wi-Fi lost"));
    }
    if (!apOn && now - staDownSince >= STA_TIMEOUT) startAP();
    if (now - lastStaAttempt >= STA_RETRY) startSTA();
}

bool netApOn() { return apOn; }

String netStatusString() {
    if (WiFi.status() == WL_CONNECTED) return "STA " + WiFi.SSID() + " " + WiFi.localIP().toString();
    if (apOn) return "AP " + WiFi.softAPIP().toString();
    return wifiSsid.length() ? "connecting " + wifiSsid : "idle";
}

String netStaString() {
    if (WiFi.status() != WL_CONNECTED) return "-";
    return WiFi.localIP().toString() + "   rssi " + String(WiFi.RSSI()) + " dBm";
}

String netApString() {
    return apOn ? String(AP_SSID) + "   " + WiFi.softAPIP().toString() : String("off");
}
