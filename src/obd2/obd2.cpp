#include "obd2/obd2.h"
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

    // Send the request frame using CANBus
    canBus->sendFrame(tx_frame);

    // Wait for the response frame
    if (canBus->readFrame(rx_frame)) {
        // Verify the response is from the ECU and matches the requested PID
        return (rx_frame.identifier == 0x7E8) && (rx_frame.data[2] == pid);
    }
    return false;
}

bool OBD2::readRPM(uint16_t &rpm) {
    twai_message_t rx_frame;
    if (requestPID(0x0C, rx_frame)) {  // 0x0C is the PID for RPM
        rpm = ((rx_frame.data[3] << 8) | rx_frame.data[4]) / 4;
        this->rpm = rpm;  // Store the RPM value
        return true;
    }
    return false;
}

bool OBD2::readThrottlePosition(uint8_t &throttle) {
    twai_message_t rx_frame;
    if (requestPID(0x11, rx_frame)) {  // 0x11 is the PID for throttle position
        throttle = rx_frame.data[3];  // Throttle position is in the third byte
        this->throttlePosition = throttle;  // Store the throttle position value
        return true;
    }
    return false;
}

bool OBD2::readSpeed(uint8_t &speed) {
    twai_message_t rx_frame;
    if (requestPID(0x0D, rx_frame)) {  // 0x0D is the PID for vehicle speed
        speed = rx_frame.data[3];  // Speed is in the third byte
        this->speed = speed;  // Store the speed value
        return true;
    }
    return false;
}

bool OBD2::readEngineTemp(int8_t &temp) {
    twai_message_t rx_frame;
    if (requestPID(0x05, rx_frame)) {  // 0x05 is the PID for engine coolant temperature
        temp = rx_frame.data[3] - 40;  // Temperature is in the third byte, offset by -40
        this->engineTemp = temp;  // Store the engine temperature value
        return true;
    }
    return false;
}

void OBD2::updateOBD2Data() {
    if (readRPM(rpm)) {
        Serial.print("RPM: ");
        Serial.println(rpm);
    } else {
        Serial.println("Failed to read RPM");
    }

    if (readThrottlePosition(throttlePosition)) {
        Serial.print("Throttle Position: ");
        Serial.println(throttlePosition);
    } else {
        Serial.println("Failed to read Throttle Position");
    }

    if (readSpeed(speed)) {
        Serial.print("Speed: ");
        Serial.println(speed);
    } else {
        Serial.println("Failed to read Speed");
    }

    if (readEngineTemp(engineTemp)) {
        Serial.print("Engine Temperature: ");
        Serial.println(engineTemp);
    } else {
        Serial.println("Failed to read Engine Temperature");
    }
}
