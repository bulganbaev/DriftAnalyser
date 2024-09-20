#include "freertos/FreeRTOS.h"
#include "front.h"
#include "config/config.h"
#include "obd2/obd2.h"
#include <WiFi.h>

#define LOG_BUFFER_SIZE 2048  // Define the log buffer size

// Create a web server object on port 80
AsyncWebServer server(80);

// Define the extern OBD2 instance
extern OBD2 obd2;



void setupAccessPoint() {
    // Start Wi-Fi in AP mode
    WiFi.softAP(AP_SSID, AP_PASSWORD);

    // Get IP address of the AP
    IPAddress IP = WiFi.softAPIP();
    Serial.println("Access Point IP Address: " + IP.toString() + "\n");

    // Serve the home page
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
        request->send(200, "text/plain", "Welcome to ESP32-S3 Access Point!");
    });

    // Route to display OBD2 data
    server.on("/getObd", HTTP_GET, handleGetObd);

    // Route to display log data

    // Start the web server
    server.begin();
}

void handleWebServer() {
    // Handle web requests (if needed)
}

// Function to handle web requests for OBD2 data
void handleGetObd(AsyncWebServerRequest *request) {
    uint16_t rpm = obd2.getRPM();
    uint8_t throttlePosition = obd2.getThrottlePosition();
    uint8_t speed = obd2.getSpeed();
    int8_t engineTemp = obd2.getEngineTemp();

    // Create a response string with OBD2 data
    String response = "RPM: " + String(rpm) +
                      "\nThrottle Position: " + String(throttlePosition) +
                      "\nSpeed: " + String(speed) +
                      "\nEngine Temperature: " + String(engineTemp);
    request->send(200, "text/plain", response);
}


