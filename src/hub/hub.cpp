#include "hub.h"
#include <LittleFS.h>
#include <FileData.h>
#include <WiFi.h>

// GyverHub object
GyverHub hub;

// External settings from led_control
int numLEDsPerStrip[NUM_STRIPS] = {276, 194, 94, 94, 94, 94};  // Make this modifiable

extern CanSettings can_setting;  // External declaration of can_setting
extern StripSettings stripSettings[NUM_STRIPS];  // External declaration of stripSettings

// Define a structure for storing settings
struct SavedData {
    CanSettings can_setting;
    StripSettings stripSettings[NUM_STRIPS];
    int numLEDsPerStrip[NUM_STRIPS];  // Add this to SavedData for saving
};

// Create an instance of SavedData for saving and loading settings
SavedData savedData = {.can_setting = {.minRPM = 2000, .maxRPM = 7000, .speed = 100, .brightess = 100}, 
                       .numLEDsPerStrip = {276, 194, 94, 94, 94, 94}};  // Initialize default CAN settings

int selectedStrip = 0;  // Variable to hold the selected LED strip for configuration

// Create a FileData object to handle saving and loading the SavedData structure
FileData fileData(&LittleFS, "/settings.dat", 'A', &savedData, sizeof(savedData));

void setupHub() {
    // Initialize the file system (for saving settings)
    if (!LittleFS.begin()) {
        Serial.println("Failed to initialize LittleFS!");
        return;  // Abort if the file system fails to start
    }
    Serial.println("LittleFS initialized");

    // Attempt to read the saved data
    if (fileData.read()) {
        Serial.println("Settings loaded successfully from file.");
    } else {
        Serial.println("Failed to load settings from file. Using default settings.");
    }

    // Apply saved settings to the global can_setting, stripSettings, and numLEDsPerStrip arrays
    can_setting = savedData.can_setting;
    for (int i = 0; i < NUM_STRIPS; i++) {
        stripSettings[i] = savedData.stripSettings[i];
        numLEDsPerStrip[i] = savedData.numLEDsPerStrip[i];
    }
    selectedStrip = 0;  // Default to the first strip

    // Start Wi-Fi in AP mode
    WiFi.mode(WIFI_AP);
    if (!WiFi.softAP(AP_SSID, AP_PASSWORD)) {
        Serial.println("Failed to start Access Point!");
        return;  // Abort if the AP fails to start
    }

    // Print the IP address of the AP
    Serial.println("Access Point started successfully");
    Serial.print("IP Address: ");
    Serial.println(WiFi.softAPIP());

    // Set up GyverHub interface
    hub.config(F("MyDevices"), F("ZverCUSTOM"), F("💡"));
    hub.onBuild(build);
    hub.begin();

    if (!hub.running()) {
        Serial.println("GyverHub failed to initialize!");
        return;  // Abort if GyverHub fails to start
    }

    Serial.println("GyverHub initialized successfully");
}

void updateHub() {
    hub.tick();
    fileData.tick();  // Save the data on timeout if needed
     static gh::Timer tmr(100);  // период 1 секунда

    // каждую секунду будем обновлять заголовок
    if (tmr) {
        hub.sendUpdate("rpm");
        hub.sendUpdate("speed");
        hub.sendUpdate("throttle");
        hub.sendUpdate("temp");
    }
    // static int lastRPM = 0;
    // int currentRPM = obd2.getRPM();
    // if (currentRPM != lastRPM) {
    //     lastRPM = currentRPM;
    //     hub.sendUpdate("rpm");
    // }

    // static int lastSpeed = 0;
    // int currentSpeed = obd2.getSpeed();
    // if (currentSpeed != lastSpeed) {
    //     lastSpeed = currentSpeed;
    //     hub.sendUpdate("speed");
    // }

    // static int lastTemp = 0;
    // int currentTemp = obd2.getEngineTemp();
    // if (currentTemp != lastTemp) {
    //     lastTemp = currentTemp;
    //     hub.sendUpdate("temp");
    // }

    // static int lastThrottle = 0;
    // int currentThrottle = obd2.getThrottlePosition();
    // if (currentThrottle != lastThrottle) {
    //     lastThrottle = currentThrottle;
    //     hub.sendUpdate("throttle");
    // }
}

void build(gh::Builder& b) {
    char buffer[64];
    
    // OBD2 Data Section
    {
        gh::Row obd2Row(b);
        String rpm = String(obd2.getRPM());
        String speed = String(obd2.getSpeed());
        b.Gauge_("rpm", &rpm).label(F("RPM")).size(3).range(0, 9000, 1);
        b.Gauge_("speed", &speed).label(F("Speed")).size(3).range(0, 300, 1);
    }

    {
        gh::Row obd2Row(b);
        String engineTemp = String(obd2.getEngineTemp());
        String throttle = String(obd2.getThrottlePosition());

        b.Gauge_("temp", &engineTemp).label(F("Temp")).size(3).range(0, 200, 1);
        b.Gauge_("throttle", &throttle).label(F("Throttle")).size(3).range(0, 100, 1);
    }

    // LED Strip Selection Section
    {
        gh::Row stripSelectRow(b);
        b.Select(&selectedStrip).label("Select LED Strip").size(3).text("0;1;2;3;4;5");

        
        snprintf(buffer, sizeof(buffer), "Strip %d Bottom", selectedStrip);
        if (stripSettings[selectedStrip].mode > 0){
            b.Switch(&stripSettings[selectedStrip].bottom).label(buffer).size(3);
            if(stripSettings[selectedStrip].bottom){
                b.Spinner(&stripSettings[selectedStrip].center).label("Middle").size(3).range(0,numLEDsPerStrip[selectedStrip],1 );
            }
        }
        b.Color(&stripSettings[selectedStrip].color).label("Color").size(3);
    }

    // Configuration for the selected LED strip
    {
        gh::Row stripConfigRow(b);
        snprintf(buffer, sizeof(buffer), "Strip %d Mode", selectedStrip);
        b.Select(&stripSettings[selectedStrip].mode).label(buffer).size(3).text("NON-RPM; RPM; HYBRID");

        snprintf(buffer, sizeof(buffer), "Strip %d Animation", selectedStrip);
        b.Select(&stripSettings[selectedStrip].animationIndex).label(buffer).size(3).text("Static Color;Theater Chase;Color Wave;Breathing Light;Rainbow Cycle;Snake;Meteor Rain;Twinkle;Running Lights");
        
        // Control the number of LEDs per strip
        snprintf(buffer, sizeof(buffer), "Strip %d LEDs", selectedStrip);
        b.Spinner(&numLEDsPerStrip[selectedStrip]).label(buffer).size(3).range(1, 1000, 1);  // Adjust range as needed

    }

    // CAN Settings
    {
        gh::Row canRow(b);
        b.Spinner(&can_setting.minRPM).label("CAN Min RPM").size(3).range(0, 8000, 100);
        b.Spinner(&can_setting.maxRPM).label("CAN Max RPM").size(3).range(0, 8000, 100);
    }

    {
        gh::Row canRow(b);
        b.Spinner(&can_setting.speed).label("Animation Speed").size(3).range(0, 100, 1);
        b.Spinner(&can_setting.brightess).label("Animation Brightness").size(3).range(0, 100, 1);
    }

    // If something changed, trigger the update
    if (b.changed()) {
        initializeLEDStrips(); 
        savedData.can_setting = can_setting;
        for (int i = 0; i < NUM_STRIPS; i++) {
            savedData.stripSettings[i] = stripSettings[i];
            savedData.numLEDsPerStrip[i] = numLEDsPerStrip[i];
        }
        // Save the data to file
        Serial.println("Data changed, saving to file...");
        fileData.update();
        hub.sendRefresh();
    }
}
