#include "net.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include "config/config.h"
#include "system/system.h"

String wifiSsid, wifiPass;

static const KnownNet knownNets[] = DEFAULT_NETWORKS;
static const int knownCount = sizeof(knownNets) / sizeof(knownNets[0]);
static int candidate = -1;   // -1 = saved creds, else index into knownNets

const char* netDefaultSsid() { return knownNets[0].ssid; }
const char* netDefaultPass() { return knownNets[0].pass; }

// saved creds first, then every configured default network, round robin
static void pickNext(String& ssid, String& pass) {
    for (int step = 0; step <= knownCount; step++) {
        candidate++;
        if (candidate >= knownCount) candidate = -1;
        if (candidate < 0) {
            if (wifiSsid.length()) { ssid = wifiSsid; pass = wifiPass; return; }
            continue;
        }
        if (!knownNets[candidate].ssid[0]) continue;
        if (wifiSsid == knownNets[candidate].ssid && wifiPass == knownNets[candidate].pass) continue;  // same as saved
        ssid = knownNets[candidate].ssid; pass = knownNets[candidate].pass; return;
    }
    ssid = wifiSsid; pass = wifiPass;
}

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
    String ssid, pass;
    pickNext(ssid, pass);
    Serial.print("Connecting to Wi-Fi: ");
    Serial.println(ssid);
    WiFi.begin(ssid.c_str(), pass.c_str());
    lastStaAttempt = millis();
}

static bool anyNetworkConfigured() {
    if (wifiSsid.length()) return true;
    for (int i = 0; i < knownCount; i++) if (knownNets[i].ssid[0]) return true;
    return false;
}

static void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
    static unsigned long lastLog = 0;
    if (event != ARDUINO_EVENT_WIFI_STA_DISCONNECTED) return;
    if (millis() - lastLog < 10000) return;  // one line per attempt burst
    lastLog = millis();
    uint8_t r = info.wifi_sta_disconnected.reason;
    const char* why = r == 201 ? "no AP found" : r == 15 ? "wrong password (handshake timeout)" : r == 202 ? "auth fail" : r == 2 ? "auth expire" : r == 8 ? "assoc leave" : "";
    sysLog("Wi-Fi STA disconnected, reason " + String(r) + " " + why);
}

void netBegin() {
    WiFi.onEvent(onWifiEvent);
    WiFi.persistent(false);  // creds live in settings.dat, don't write NVS on every boot
    WiFi.setAutoReconnect(false);
    WiFi.setSleep(false);    // modem sleep adds 100-300 ms to every HTTP request
    WiFi.setHostname("zvercustom");
    if (!anyNetworkConfigured()) {
        startAP();
        return;
    }
    WiFi.mode(WIFI_STA);
    staDownSince = millis();
    candidate = -1 - 1;  // so the first pick lands on saved creds
    startSTA();
}

void netReconnect() {
    candidate = -1 - 1;
    if (!anyNetworkConfigured()) {
        WiFi.disconnect();
        startAP();
        return;
    }
    if (!apOn) WiFi.mode(WIFI_STA);
    staDownSince = millis();
    startSTA();
}

void netTick() {
    if (!anyNetworkConfigured()) return;
    unsigned long now = millis();

    if (WiFi.status() == WL_CONNECTED) {
        if (staDownSince) {
            staDownSince = 0;
            sysLog("Wi-Fi connected " + WiFi.SSID() + " " + WiFi.localIP().toString());
            if (MDNS.begin("zvercustom")) MDNS.addService("http", "tcp", 80);
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
    return anyNetworkConfigured() ? "connecting" : "idle";
}

String netStaString() {
    if (WiFi.status() != WL_CONNECTED) return "-";
    return WiFi.localIP().toString() + "   rssi " + String(WiFi.RSSI()) + " dBm";
}

String netApString() {
    return apOn ? String(AP_SSID) + "   " + WiFi.softAPIP().toString() : String("off");
}
