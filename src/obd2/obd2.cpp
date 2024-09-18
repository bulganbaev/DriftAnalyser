#include "obd2.h"
#include <Arduino.h>

void OBD2::begin(CANBus &can) {
    this->canBus = &can;
}

bool OBD2::requestPID(uint8_t pid, twai_message_t &rx_frame) {
    // Create a request frame for the given PID
    twai_message_t tx_frame;
    tx_frame.flags = 0;  // Standard frame
    tx_frame.identifier = 0x7DF;  // OBD2 request ID for all ECUs
    tx_frame.data_length_code = 8;  // Data length
    tx_frame.data[0] = 0x02;  // Number of additional data bytes
    tx_frame.data[1] = 0x01;  // Service ID: Show current data
    tx_frame.data[2] = pid;   // PID to request
    tx_frame.data[3] = 0x00;
    tx_frame.data[4] = 0x00;
    tx_frame.data[5] = 0x00;
    tx_frame.data[6] = 0x00;
    tx_frame.data[7] = 0x00;

    // Send request
    canBus->sendFrame(tx_frame);

    // Wait for response
    unsigned long timeout = millis() + 1000;  // 1 second timeout
    while (millis() < timeout) {
        if (canBus->readFrame(rx_frame)) {
            if (rx_frame.identifier == 0x7E8) {  // Response from ECU
                return true;
            }
        }
    }

    return false;
}

bool OBD2::readRPM(uint16_t &rpm) {
    twai_message_t rx_frame;  // Use `twai_message_t` for frames
    if (requestPID(0x0C, rx_frame)) {  // 0x0C is the PID for RPM
        // RPM is stored in the first two data bytes of the response
        rpm = ((rx_frame.data[3] << 8) | rx_frame.data[4]) / 4;
        return true;
    }
    return false;
}

bool OBD2::readThrottlePosition(uint8_t &throttle) {
    twai_message_t rx_frame;
    if (requestPID(0x11, rx_frame)) {  // 0x11 is the PID for throttle position
        throttle = rx_frame.data[3];  // Throttle position is in the third byte
        return true;
    }
    return false;
}
