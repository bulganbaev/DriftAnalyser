#include "can_bus.h"
#include <Arduino.h>

void CANBus::begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig) {
    this->stbPin = stbPin;
    pinMode(stbPin, OUTPUT);
    digitalWrite(stbPin, LOW); // Set STB pin low to activate CAN transceiver

    // Install TWAI driver
    twai_general_config_t generalConfig = TWAI_GENERAL_CONFIG_DEFAULT((gpio_num_t)txPin, (gpio_num_t)rxPin, TWAI_MODE_NORMAL);
    twai_filter_config_t filterConfig = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    // Initialize TWAI driver
    if (twai_driver_install(&generalConfig, &timingConfig, &filterConfig) == ESP_OK) {
        Serial.println("TWAI driver installed");
    } else {
        Serial.println("Failed to install TWAI driver");
    }

    // Start TWAI driver
    if (twai_start() == ESP_OK) {
        Serial.println("TWAI driver started");
    } else {
        Serial.println("Failed to start TWAI driver");
    }
}

bool CANBus::readFrame(twai_message_t &rx_frame) {
    // Read TWAI (CAN) frame
    if (twai_receive(&rx_frame, pdMS_TO_TICKS(1000)) == ESP_OK) {
        return true;
    }
    return false;
}

void CANBus::sendFrame(twai_message_t &tx_frame) {
    // Send TWAI (CAN) frame
    twai_transmit(&tx_frame, pdMS_TO_TICKS(1000));
}
