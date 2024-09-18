#ifndef OBD2_H
#define OBD2_H

#include "can_bus/can_bus.h"
#include "driver/twai.h"  // Include TWAI driver

class OBD2 {
public:
    void begin(CANBus &can);
    bool readRPM(uint16_t &rpm);
    bool readThrottlePosition(uint8_t &throttle);

private:
    CANBus *canBus;
    bool requestPID(uint8_t pid, twai_message_t &rx_frame);  // Use `twai_message_t` for CAN frames
};

#endif // OBD2_H
