#ifndef CAN_BUS_H
#define CAN_BUS_H

#include <Arduino.h>
#include "driver/twai.h"  // TWAI (CAN) driver

// supported bit rates, index into CANBus::TIMINGS
enum CanBitrate : int { BR_500K = 0, BR_250K, BR_125K, BR_100K, BR_1M, BR_COUNT };

class CANBus {
public:
    void begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig, bool listenOnly = false);
    // stop, uninstall and bring the driver back in the requested mode
    void restart(bool listenOnly);
    void restart(bool listenOnly, int bitrate);
    int bitrate() const { return bitrateIdx; }
    static const char* bitrateName(int idx);
    static twai_timing_config_t timingFor(int idx);
    unsigned long busErrors() const;
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
    int bitrateIdx = BR_500K;
    bool listenOnly = false;
    bool connected = false;    // driver installed and started
};

#endif // CAN_BUS_H
