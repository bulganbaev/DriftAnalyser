#include <Arduino.h>
#include "led_control/led_control.h"
#include "obd2/obd2.h"
#include "can_bus/can_bus.h"
#include "hub/hub.h"

CANBus canBus;
OBD2 obd2;

void setup() {
    Serial.begin(115200);
    delay(2000);
    // Log the start of the system
    Serial.println("System initializing...\n");

    // Initialize LED strips or other setup tasks
    initializeLEDStrips();
    Serial.println("LED strips initialized\n");

    // Configure CAN bus timing and initialize
    twai_timing_config_t timingConfig = TWAI_TIMING_CONFIG_500KBITS();
    canBus.begin(CAN_RX_PIN, CAN_TX_PIN, CAN_STB_PIN, timingConfig);
    Serial.println("CAN bus initialized\n");

    // Initialize the OBD2 communication
    obd2.begin(canBus);
    Serial.println("OBD2 initialized\n");

    setupHub();

}

void loop() {
    updateHub();
    // Update OBD2 data and log it
    obd2.updateOBD2Data();
    // Run LED animations or other tasks
    runAnimations();
    

}
