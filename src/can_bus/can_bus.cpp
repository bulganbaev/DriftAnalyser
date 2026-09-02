#include "can_bus.h"
#include <Arduino.h>

void CANBus::begin(int rxPin, int txPin, int stbPin, twai_timing_config_t timingConfig, bool listenOnly) {
    this->rxPin = rxPin;
    this->txPin = txPin;
    this->stbPin = stbPin;
    this->timing = timingConfig;
    this->listenOnly = listenOnly;

    pinMode(stbPin, OUTPUT);
    digitalWrite(stbPin, LOW); // Set STB pin low to activate CAN transceiver

    install();
}

void CANBus::install() {
    connected = false;
    twai_mode_t mode = listenOnly ? TWAI_MODE_LISTEN_ONLY : TWAI_MODE_NORMAL;
    twai_general_config_t generalConfig = TWAI_GENERAL_CONFIG_DEFAULT((gpio_num_t)txPin, (gpio_num_t)rxPin, mode);
    generalConfig.rx_queue_len = 32;
    twai_filter_config_t filterConfig = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    if (twai_driver_install(&generalConfig, &timing, &filterConfig) != ESP_OK) {
        Serial.println("Failed to install TWAI driver");
        return;
    }
    if (twai_start() != ESP_OK) {
        Serial.println("Failed to start TWAI driver");
        twai_driver_uninstall();
        return;
    }
    connected = true;
    Serial.println(listenOnly ? "TWAI started (listen only)" : "TWAI started (normal)");
}

void CANBus::restart(bool listenOnly) {
    if (connected) {
        twai_stop();
        twai_driver_uninstall();
        connected = false;
    }
    this->listenOnly = listenOnly;
    install();
}

String CANBus::stateName() const {
    if (!connected) return F("off");
    twai_status_info_t st;
    if (twai_get_status_info(&st) != ESP_OK) return F("?");
    switch (st.state) {
        case TWAI_STATE_RUNNING:    return F("running");
        case TWAI_STATE_BUS_OFF:    return F("bus-off");
        case TWAI_STATE_RECOVERING: return F("recovering");
        default:                    return F("stopped");
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

bool CANBus::readFrame(twai_message_t &rx_frame, uint32_t timeoutMs) {
    if (!connected) return false;
    return twai_receive(&rx_frame, pdMS_TO_TICKS(timeoutMs)) == ESP_OK;
}

void CANBus::sendFrame(twai_message_t &tx_frame) {
    if (!connected || listenOnly) return;
    twai_transmit(&tx_frame, pdMS_TO_TICKS(10));
}
