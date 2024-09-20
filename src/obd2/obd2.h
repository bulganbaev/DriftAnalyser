#ifndef OBD2_H
#define OBD2_H

#include "can_bus/can_bus.h"
#include "driver/twai.h"  // Include TWAI driver
#include "front/front.h"

class OBD2 {
public:
    // Initialize OBD2 with CAN bus object
    void begin(CANBus &can);

    // Read RPM value from the OBD2 system
    bool readRPM(uint16_t &rpm);

    // Read throttle position value from the OBD2 system
    bool readThrottlePosition(uint8_t &throttle);

    // Read vehicle speed from the OBD2 system
    bool readSpeed(uint8_t &speed);

    // Read engine coolant temperature from the OBD2 system
    bool readEngineTemp(int8_t &temp);

    // Update all OBD2 data (for printing and web server)
    void updateOBD2Data();

    // Getters for the current OBD2 values
    uint16_t getRPM() const { return rpm; }
    uint8_t getThrottlePosition() const { return throttlePosition; }
    uint8_t getSpeed() const { return speed; }
    int8_t getEngineTemp() const { return engineTemp; }

private:
    CANBus *canBus;  // Pointer to CAN bus object

    // Helper function to request PID and receive CAN frame
    bool requestPID(uint8_t pid, twai_message_t &rx_frame);

    uint16_t rpm = 0;
    uint8_t throttlePosition = 0;
    uint8_t speed = 0;
    int8_t engineTemp = 0;
};

#endif // OBD2_H
