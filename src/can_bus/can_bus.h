#ifndef CAN_BUS_H
#define CAN_BUS_H

#include <Arduino.h>
#include "driver/twai.h"  // TWAI (CAN) driver

class CANBus {
public:
    void begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig);
    bool readFrame(twai_message_t &rx_frame);
    void sendFrame(twai_message_t &tx_frame);
    
    // Public method to check if the CAN bus is connected and active
    bool isConnected() const;

private:
    int stbPin;        // STB pin to control CAN transceiver
    bool connected;    // Connection status of CAN bus
};

#endif // CAN_BUS_H
