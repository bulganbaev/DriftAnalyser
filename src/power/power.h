#ifndef POWER_H
#define POWER_H

#include <Arduino.h>

// LED supply switch (BTS7002) with a software latch, VBAT and the status LED
struct PowerState {
    float vbat = 0;      // V, smoothed
    float ledAmps = 0;   // A, smoothed
    float isVolts = 0;   // raw IS voltage, last sample
    bool on = false;     // switch is driven on
    bool latched = false;
    String reason;       // why the latch tripped
};

extern PowerState power;

void powerBegin();       // switch off, status LED on until the first powerTick
void powerTick();
void powerResetLatch();
String powerStatusString();

#endif
