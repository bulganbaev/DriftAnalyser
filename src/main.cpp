#include <Arduino.h>
#include "settings/settings.h"
#include "led_control/led_control.h"
#include "obd2/obd2.h"
#include "can_bus/can_bus.h"
#include "hub/hub.h"
#include "net/net.h"
#include "vehicle/vehicle.h"
#include "imu/imu.h"

CANBus canBus;
OBD2 obd2;

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("System initializing...");

    settingsBegin();
    initializeLEDStrips();

    twai_timing_config_t timingConfig = TWAI_TIMING_CONFIG_500KBITS();
    canBus.begin(CAN_RX_PIN, CAN_TX_PIN, CAN_STB_PIN, timingConfig, canMode != CAN_MODE_OBD2);
    obd2.begin(canBus);
    vehicleSetup(canBus, obd2);

    netBegin();
    setupHub();
    imuSetup();
    Serial.println("Ready");
}

void loop() {
    netTick();
    settingsTick();
    updateHub();
    vehicleTick();
    imuTick();
    runAnimations();
}
