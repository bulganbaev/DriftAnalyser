#ifndef NET_H
#define NET_H

#include <Arduino.h>

// STA to the saved network, own AP as fallback
extern String wifiSsid;
extern String wifiPass;

struct KnownNet { const char* ssid; const char* pass; };
const char* netDefaultSsid();
const char* netDefaultPass();

void netBegin();
void netTick();
void netReconnect();
bool netApOn();
String netStatusString();  // mode + ssid + ip
String netStaString();     // ip + rssi or "-"
String netApString();      // ap ssid + ip or "off"

#endif
