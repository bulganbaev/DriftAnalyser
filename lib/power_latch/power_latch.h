#pragma once
// LED supply switch protection logic for PCB v2 (BTS7002-1EPP), no Arduino deps.
#include <stdint.h>

// IS: kILIS 22700, 470R to GND
inline float isVoltsToAmps(float v) { return v * 22700.0f / 470.0f; }
// VBAT divider 47k / 10k
inline float vbatFromAdc(float v) { return v * 5.7f; }

// Debounce for the two reasons to cut the strips: current above the limit (strips
// inrush for a few ms at switch-on, so it must hold) and the switch's own fault
// signal, which pushes IS into the 3V3 clamp.
class PowerLatch {
public:
    enum Trip { NONE, OVERCURRENT, FAULT };
    static constexpr uint32_t OVER_MS = 100;
    static constexpr uint32_t FAULT_MS = 50;
    static constexpr float FAULT_VOLTS = 2.8f;

    // call while the switch is on
    Trip update(uint32_t now, float amps, float isVolts, float maxAmps) {
        if (isVolts > FAULT_VOLTS) {
            if (!faultActive) {
                faultActive = true;
                faultSince = now;
            }
            if (now - faultSince >= FAULT_MS) return FAULT;
        } else {
            faultActive = false;
        }
        if (amps > maxAmps) {
            if (!overActive) {
                overActive = true;
                overSince = now;
            }
            if (now - overSince >= OVER_MS) return OVERCURRENT;
        } else {
            overActive = false;
        }
        return NONE;
    }

    void reset() { overActive = faultActive = false; }

private:
    bool overActive = false;
    bool faultActive = false;
    uint32_t overSince = 0;
    uint32_t faultSince = 0;
};
