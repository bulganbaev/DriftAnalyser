#ifndef SYSTEM_H
#define SYSTEM_H

#include <Arduino.h>

// Boot info and a small persistent log on LittleFS
void sysBegin();                 // call after LittleFS is mounted
void sysLog(const String& msg);  // Serial + /log.txt with uptime prefix
String sysLogTail(int maxBytes = 2500);
void sysClearLog();
String sysResetReason();
String sysUptime();
String sysBuildInfo();

#endif
