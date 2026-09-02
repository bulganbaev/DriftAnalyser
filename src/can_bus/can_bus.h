#ifndef CAN_BUS_H
#define CAN_BUS_H

#include <Arduino.h>
#include "driver/twai.h"  // TWAI (CAN) driver

class CANBus {
public:
    void begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig, bool listenOnly = false);
    // stop, uninstall and bring the driver back in the requested mode
    void restart(bool listenOnly);
    bool readFrame(twai_message_t &rx_frame, uint32_t timeoutMs = 10);
    void sendFrame(twai_message_t &tx_frame);

    bool isDriverRunning() const { return connected; }
    bool isListenOnly() const { return listenOnly; }
    String stateName() const;
    String diagString() const;   // state + error counters

    // Public method to check if the CAN bus is connected and active
    bool isConnected() const;

private:
    void install();

    int rxPin = -1;
    int txPin = -1;
    int stbPin = -1;
    twai_timing_config_t timing;
    bool listenOnly = false;
    bool connected = false;    // driver installed and started
};

#endif // CAN_BUS_H
