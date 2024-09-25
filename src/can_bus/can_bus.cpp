#include "can_bus.h"
#include <Arduino.h>

void CANBus::begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig) {
    this->stbPin = stbPin;
    pinMode(stbPin, OUTPUT);
    digitalWrite(stbPin, LOW); // Set STB pin low to activate CAN transceiver

    connected = false; // Initially, not connected

    // Install TWAI driver
    twai_general_config_t generalConfig = TWAI_GENERAL_CONFIG_DEFAULT((gpio_num_t)txPin, (gpio_num_t)rxPin, TWAI_MODE_NORMAL);
    twai_filter_config_t filterConfig = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    // Initialize TWAI driver
    if (twai_driver_install(&generalConfig, &timingConfig, &filterConfig) == ESP_OK) {
        Serial.println("TWAI driver installed");
    } else {
        Serial.println("Failed to install TWAI driver");
        return; // Return early if installation fails
    }

    // Start TWAI driver
    if (twai_start() == ESP_OK) {
        Serial.println("TWAI driver started");
        connected = true;  // Set connected to true when successfully started
    } else {
        Serial.println("Failed to start TWAI driver");
        connected = false;
    }
}

// Modified isConnected() to check for received messages or errors
bool CANBus::isConnected() const {
    if (!connected) {
        return false; // Not connected if driver isn't running
    }

    twai_status_info_t status_info;
    twai_get_status_info(&status_info);

    // Check if there are messages to read or if the bus is in an error state
    if (status_info.state == TWAI_STATE_RUNNING && status_info.msgs_to_rx > 0) {
        return true;  // Bus is active and receiving frames
    } else if (status_info.state != TWAI_STATE_RUNNING || status_info.bus_error_count > 0) {
        return false; // Either bus is off or there are bus errors
    }

    return false;  // Default to not connected
}

bool CANBus::readFrame(twai_message_t &rx_frame) {
    if (!connected) {
        Serial.println("Cannot read, CAN bus not connected");
        return false;
    }

    // Read TWAI (CAN) frame
    if (twai_receive(&rx_frame, pdMS_TO_TICKS(1)) == ESP_OK) {
        return true;
    }
    return false;
}

void CANBus::sendFrame(twai_message_t &tx_frame) {
    if (!connected) {
        Serial.println("Cannot send, CAN bus not connected");
        return;
    }

    // Send TWAI (CAN) frame
    twai_transmit(&tx_frame, pdMS_TO_TICKS(1));
}
