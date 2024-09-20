#include <Arduino.h>
#include "front/front.h"
#include "led_control/led_control.h"
#include "obd2/obd2.h"
#include "can_bus/can_bus.h"

CANBus canBus;
OBD2 obd2;

void setup() {
    Serial.begin(115200);

    // Log the start of the system
    Serial.println("System initializing...\n");

    // Set up the access point and web server
    setupAccessPoint();

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
}

void loop() {
    // Handle the web server
    handleWebServer();

    // Update OBD2 data and log it
    obd2.updateOBD2Data();

    // Run LED animations or other tasks
    runAnimations();

    // Display LED effects
    FastLED.show();

    // Adjust delay for controlling animation speed
    delay(50);
}
