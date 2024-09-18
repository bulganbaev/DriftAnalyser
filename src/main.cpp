#include <Arduino.h>
#include "wifi_manager/wifi_manager.h"
#include "pins/pins.h"
#include "led_control/led_control.h"
#include "gps_controller/gps_controller.h"
#include "can_bus/can_bus.h"
#include "obd2/obd2.h"
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

CANBus canBus;
OBD2 obd2;

AsyncWebServer server(80);  // Create a web server object on port 80

uint16_t rpm = 0;
uint8_t throttlePosition = 0;

// Function to handle OBD2 data updates
void updateOBD2Data() {
    if (obd2.readRPM(rpm)) {
        Serial.print("RPM: ");
        Serial.println(rpm);
    } else {
        Serial.println("Failed to read RPM");
    }

    if (obd2.readThrottlePosition(throttlePosition)) {
        Serial.print("Throttle Position: ");
        Serial.println(throttlePosition);
    } else {
        Serial.println("Failed to read Throttle Position");
    }
}

// Function to handle web requests for OBD2 data
void handleGetObd(AsyncWebServerRequest *request) {
    String response = "RPM: " + String(rpm) + "\nThrottle Position: " + String(throttlePosition);
    request->send(200, "text/plain", response);
}

void setup() {
    Serial.begin(115200);

    // Настраиваем пин кнопки BOOT
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_FLASH_PIN, OUTPUT);

    // Инициализация Wi-Fi через WiFiManager
    WiFiManagerSetup();

    // Initialize LED strips
    initializeLEDStrips();

    // Configure CAN bus timing and initialize
    twai_timing_config_t timingConfig = TWAI_TIMING_CONFIG_500KBITS();
    canBus.begin(CAN_RX_PIN, CAN_TX_PIN, CAN_STB_PIN, timingConfig);

    // Initialize the GPS module
    initializeGPS();

    // Initialize OBD2 communication
    obd2.begin(canBus);

    // Web server routes
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->send(200, "text/plain", "Hello, this is the ESP32-S3 Web Server!");
    });

    // Route to display OBD2 data (RPM and Throttle Position)
    server.on("/getObd", HTTP_GET, handleGetObd);

    // Start the server
    server.begin();
}

void loop() {
    // Update OBD2 data
    updateOBD2Data();

    // Check Wi-Fi and BOOT button status
    WiFiManagerLoop();

    // Run LED animations
    runAnimations();

    // Show the LED effects
    FastLED.show();

    // Adjust delay for animation speed control
    delay(50);
}
