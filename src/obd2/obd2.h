#ifndef OBD2_H
#define OBD2_H

#include "can_bus/can_bus.h"
#include "driver/twai.h"

// Non-blocking OBD2 mode 01 poller. Results land in the shared VehicleData.
class OBD2 {
public:
    void begin(CANBus &can);
    void tick();

    // Getters read the shared vehicle data (filled by OBD2 or BMW decoder)
    uint16_t getRPM() const;
    uint8_t getThrottlePosition() const;
    uint8_t getSpeed() const;
    int8_t getEngineTemp() const;

private:
    void sendRequest(uint8_t pid);
    bool handleFrame(const twai_message_t &f, uint8_t pid);

    CANBus *canBus = nullptr;
    bool waiting = false;
    uint8_t pidIndex = 0;
    unsigned long sentAt = 0;
    unsigned long lastSend = 0;
};

#endif // OBD2_H
