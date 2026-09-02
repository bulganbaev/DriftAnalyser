#ifndef NET_H
#define NET_H

#include <Arduino.h>

// STA to the saved network, own AP as fallback
extern String wifiSsid;
extern String wifiPass;

void netBegin();
void netTick();
void netReconnect();
bool netApOn();
String netStatusString();  // mode + ssid + ip
String netStaString();     // ip + rssi or "-"
String netApString();      // ap ssid + ip or "off"

#endif
