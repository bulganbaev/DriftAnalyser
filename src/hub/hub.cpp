#include "hub.h"
#include <LittleFS.h>
#include <FileData.h>
#include <WiFi.h>
#include "vehicle/vehicle.h"
#include "imu/imu.h"

// GyverHub object
GyverHub hub;

// External settings from led_control
int numLEDsStrip1 = 276;
int numLEDsStrip2 = 194;
int numLEDsStrip3 = 94;
int numLEDsStrip4 = 94;
int numLEDsStrip5 = 94;
int numLEDsStrip6 = 94;

extern CanSettings can_setting;  // External declaration of can_setting
extern StripSettings stripSettings[NUM_STRIPS];  // External declaration of stripSettings

unsigned long lastUpdate = 0;
const unsigned long updateInterval = 1000;  // 1 second interval

// Define a structure for storing settings
struct SavedData {
    CanSettings can_setting;
    StripSettings stripSettings[NUM_STRIPS];
    int numLEDsStrip1;
    int numLEDsStrip2;
    int numLEDsStrip3;
    int numLEDsStrip4;
    int numLEDsStrip5;
    int numLEDsStrip6;
    char wifiSsid[33];
    char wifiPass[65];
    int canMode;
};

// Create an instance of SavedData for saving and loading settings
SavedData savedData = {
    .can_setting = {.minRPM = 2000, .maxRPM = 7000, .speed = 100, .brightess = 100},
    .numLEDsStrip1 = 276,
    .numLEDsStrip2 = 194,
    .numLEDsStrip3 = 94,
    .numLEDsStrip4 = 94,
    .numLEDsStrip5 = 94,
    .numLEDsStrip6 = 94
};

int selectedStrip = 0;  // Variable to hold the selected LED strip for configuration
int numLedsPerStrip[6] = {numLEDsStrip1, numLEDsStrip2, numLEDsStrip3, numLEDsStrip4, numLEDsStrip5, numLEDsStrip6};

// Create a FileData object to handle saving and loading the SavedData structure
FileData fileData(&LittleFS, "/settings.dat", 'A', &savedData, sizeof(savedData));

// Wi-Fi: STA to saved network, own AP as fallback
String wifiSsid, wifiPass;
static bool apOn = false;
static unsigned long staDownSince = 0;   // 0 = connected
static unsigned long lastStaAttempt = 0;
const unsigned long STA_TIMEOUT = 20000;  // no STA this long -> raise AP
const unsigned long STA_RETRY = 30000;    // retry STA while AP is on

static void startAP() {
    if (apOn) return;
    WiFi.mode(wifiSsid.length() ? WIFI_AP_STA : WIFI_AP);
    if (WiFi.softAP(AP_SSID, AP_PASSWORD)) {
        apOn = true;
        Serial.print("AP started, IP: ");
        Serial.println(WiFi.softAPIP());
    } else {
        Serial.println("Failed to start Access Point!");
    }
}

static void stopAP() {
    if (!apOn) return;
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    apOn = false;
    Serial.println("AP stopped");
}

static void startSTA() {
    Serial.print("Connecting to Wi-Fi: ");
    Serial.println(wifiSsid);
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
    lastStaAttempt = millis();
}

static void wifiSetup() {
    WiFi.setAutoReconnect(false);
    if (!wifiSsid.length()) {
        startAP();
        return;
    }
    WiFi.mode(WIFI_STA);
    staDownSince = millis();
    startSTA();
}

static void wifiReconnect() {
    if (!wifiSsid.length()) {
        WiFi.disconnect();
        startAP();
        return;
    }
    if (!apOn) WiFi.mode(WIFI_STA);
    staDownSince = millis();
    startSTA();
}

static void wifiTick() {
    if (!wifiSsid.length()) return;
    unsigned long now = millis();

    if (WiFi.status() == WL_CONNECTED) {
        if (staDownSince) {
            staDownSince = 0;
            Serial.print("Wi-Fi connected, IP: ");
            Serial.println(WiFi.localIP());
        }
        stopAP();
        return;
    }

    if (!staDownSince) {
        staDownSince = now;
        Serial.println("Wi-Fi lost");
    }
    if (!apOn && now - staDownSince >= STA_TIMEOUT) startAP();
    if (now - lastStaAttempt >= STA_RETRY) startSTA();
}

void formatLittleFS() {
    Serial.println("Formatting LittleFS...");
    LittleFS.format();  // This will erase all data on LittleFS and format it
}

void compareFiles(const char* file1, const char* file2) {
    File f1 = LittleFS.open(file1, "r");
    File f2 = LittleFS.open(file2, "r");

    if (!f1 || !f2) {
        Serial.println("Failed to open one or both files for comparison.");
        return;
    }

    size_t fileSize1 = f1.size();
    size_t fileSize2 = f2.size();

    if (fileSize1 != fileSize2) {
        Serial.printf("Files %s and %s have different sizes.\n", file1, file2);
        f1.close();
        f2.close();
        return;
    }

    bool identical = true;
    while (f1.available() && f2.available()) {
        char byte1 = f1.read();
        char byte2 = f2.read();

        if (byte1 != byte2) {
            identical = false;
            Serial.printf("Difference at byte %ld: %02X != %02X\n", f1.position(), byte1, byte2);
        }
    }

    if (identical) {
        Serial.printf("Files %s and %s are identical.\n", file1, file2);
    } else {
        Serial.printf("Files %s and %s are different.\n", file1, file2);
    }

    f1.close();
    f2.close();
}

void setupHub() {
    // Initialize the file system (for saving settings)
    if (!LittleFS.begin()) {
        Serial.println("Failed to initialize LittleFS!");
        formatLittleFS();  // Format if mounting fails
        if (!LittleFS.begin()) {
            Serial.println("Failed to mount LittleFS after formatting!");
            return;  // Abort if the file system fails to start after formatting
        }
    }
    Serial.println("LittleFS initialized");

    // Check if the settings file exists
    if (!LittleFS.exists("/settings2.dat")) {
        Serial.println("/settings2.dat does not exist, creating a new one...");
        File file = LittleFS.open("/settings2.dat", "w");  // Create the file if it doesn't exist
        if (!file) {
            Serial.println("Failed to create /settings2.dat!");
            return;  // Abort if the file cannot be created
        }
        file.close();  // Close the file after creating it
    }
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
        
    }
    numLEDsStrip1 = savedData.numLEDsStrip1;
    numLEDsStrip2 = savedData.numLEDsStrip2;
    numLEDsStrip3 = savedData.numLEDsStrip3;
    numLEDsStrip4 = savedData.numLEDsStrip4;
    numLEDsStrip5 = savedData.numLEDsStrip5;
    numLEDsStrip6 = savedData.numLEDsStrip6;
    numLedsPerStrip[0] = savedData.numLEDsStrip1;
    numLedsPerStrip[1] = savedData.numLEDsStrip2;
    numLedsPerStrip[2] = savedData.numLEDsStrip3;
    numLedsPerStrip[3] = savedData.numLEDsStrip4;
    numLedsPerStrip[4] = savedData.numLEDsStrip5;
    numLedsPerStrip[5] = savedData.numLEDsStrip6;
    for (int i = 0; i < NUM_STRIPS; i++) init(i);  // apply saved LED counts to FastLED
    selectedStrip = 0;  // Default to the first strip
    savedData.wifiSsid[sizeof(savedData.wifiSsid) - 1] = 0;
    savedData.wifiPass[sizeof(savedData.wifiPass) - 1] = 0;
    wifiSsid = savedData.wifiSsid;
    wifiPass = savedData.wifiPass;
    canMode = constrain(savedData.canMode, 0, 2);

    wifiSetup();


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
    wifiTick();
    hub.tick();
    fileData.tick();  // Save the data on timeout if needed
    unsigned long currentTime = millis();
    
    if (currentTime - lastUpdate >= updateInterval) {
        lastUpdate = currentTime;
        hub.sendUpdate("rpm");
        hub.sendUpdate("speed");
        hub.sendUpdate("throttle");
        hub.sendUpdate("temp");
        hub.sendUpdate("wifi");
        hub.sendUpdate("can");
        hub.sendUpdate("sta");
        hub.sendUpdate("ap");
        if (imu.ok && hub.menu == 4) {
            const char* names[] = {"ax", "ay", "az", "gx", "gy", "gz", "imutemp"};
            for (const char* n : names) hub.sendUpdate(n);
        }
        if (canMode == CAN_MODE_SNIFFER) hub.sendUpdate("sniff");
    }
    
}

static String wifiStatusString() {
    if (WiFi.status() == WL_CONNECTED) return "STA " + WiFi.SSID() + " " + WiFi.localIP().toString();
    if (apOn) return "AP " + WiFi.softAPIP().toString();
    return wifiSsid.length() ? "connecting " + wifiSsid : "idle";
}

static void applyToAllStrips(int from) {
    for (int i = 0; i < NUM_STRIPS; i++) {
        if (i == from) continue;
        stripSettings[i].mode = stripSettings[from].mode;
        stripSettings[i].animationIndex = stripSettings[from].animationIndex;
        stripSettings[i].color = stripSettings[from].color;
        stripSettings[i].colorOrder = stripSettings[from].colorOrder;
        stripSettings[i].bottom = stripSettings[from].bottom;
        stripSettings[i].center = stripSettings[from].center;
    }
}

static void buildDashboard(gh::Builder& b) {
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
    {
        gh::Row statusRow(b);
        b.Label_("wifi", wifiStatusString()).label(F("Wi-Fi")).size(3);
        b.Label_("can", canStatusString()).label(F("CAN")).size(3);
    }
    {
        gh::Row rebootRow(b);
        if (b.Button().label("Reboot").size(3).click()) {
            fileData.updateNow();
            delay(100);
            ESP.restart();
        }
    }
}

static void buildLeds(gh::Builder& b, bool& forceSave) {
    char buffer[64];
    {
        gh::Row stripSelectRow(b);
        b.Select(&selectedStrip).label("Select LED Strip").size(3).text("0;1;2;3;4;5");

        snprintf(buffer, sizeof(buffer), "Strip %d Bottom", selectedStrip);
        if (stripSettings[selectedStrip].mode > 0) {
            b.Switch(&stripSettings[selectedStrip].bottom).label(buffer).size(3);
            if (stripSettings[selectedStrip].bottom) {
                b.Spinner(&stripSettings[selectedStrip].center).label("Middle").size(3).range(0, numLedsPerStrip[selectedStrip], 1);
            }
        }
        b.Color(&stripSettings[selectedStrip].color).label("Color").size(3);
    }
    {
        gh::Row stripConfigRow(b);
        snprintf(buffer, sizeof(buffer), "Strip %d Mode", selectedStrip);
        b.Select(&stripSettings[selectedStrip].mode).label(buffer).size(3).text("NON-RPM; RPM; HYBRID");

        snprintf(buffer, sizeof(buffer), "Strip %d Color Order", selectedStrip);
        b.Select(&stripSettings[selectedStrip].colorOrder).label(buffer).size(3).text("RGB;GRB;BGR;RBG;GBR;BRG");

        snprintf(buffer, sizeof(buffer), "Strip %d Animation", selectedStrip);
        b.Select(&stripSettings[selectedStrip].animationIndex).label(buffer).size(3).text("Static Color;Theater Chase;Color Wave;Breathing Light;Rainbow Cycle;Snake;Meteor Rain;Twinkle;Running Lights;Larson Scanner;Fire;Police;Confetti;Color Wipe;Sinelon");

        snprintf(buffer, sizeof(buffer), "Strip %d LEDs", selectedStrip);
        b.Spinner(&numLedsPerStrip[selectedStrip]).label(buffer).size(3).range(1, MAX_LEDS, 1);

        if (b.Button().label("Apply to all strips").size(3).click()) {
            applyToAllStrips(selectedStrip);
            forceSave = true;
        }
    }
    {
        gh::Row rpmRow(b);
        b.Spinner(&can_setting.minRPM).label("Scale Min RPM").size(3).range(0, 8000, 100);
        b.Spinner(&can_setting.maxRPM).label("Scale Max RPM").size(3).range(0, 8000, 100);
    }
    {
        gh::Row animRow(b);
        b.Spinner(&can_setting.speed).label("Animation Speed").size(3).range(0, 100, 1);
        b.Spinner(&can_setting.brightess).label("Animation Brightness").size(3).range(0, 100, 1);
    }
}

static void buildCan(gh::Builder& b) {
    {
        gh::Row canModeRow(b);
        if (b.Select(&canMode).label("CAN Source").size(3).text("OBD2;BMW MS43;Sniffer").click()) {
            vehicleSetMode(canMode);
        }
        b.Label_("can", canStatusString()).label(F("CAN")).size(3);
    }
    {
        gh::Row rpmRow(b);
        b.Label_("rpm", String(obd2.getRPM())).label(F("RPM")).size(2);
        b.Label_("speed", String(obd2.getSpeed())).label(F("Speed")).size(2);
        b.Label_("temp", String(obd2.getEngineTemp())).label(F("Temp")).size(2);
        b.Label_("throttle", String(obd2.getThrottlePosition())).label(F("Throttle")).size(2);
    }
    if (canMode == CAN_MODE_SNIFFER) {
        gh::Row sniffRow(b);
        b.Text_("sniff", sniffTableString()).label(F("CAN frames")).rows(20).size(6);
    }
}

static void buildWifi(gh::Builder& b) {
    {
        gh::Row wifiRow(b);
        b.Input(&wifiSsid).label("Wi-Fi SSID").size(3).maxLen(32);
        b.Pass(&wifiPass).label("Wi-Fi Password").size(3).maxLen(64);
        if (b.Button().label("Reconnect").size(2).click()) {
            wifiReconnect();
        }
    }
    {
        gh::Row statusRow(b);
        b.Label_("wifi", wifiStatusString()).label(F("Status")).size(3);
        String sta = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() + "  rssi " + String(WiFi.RSSI()) : String("-");
        b.Label_("sta", sta).label(F("STA IP")).size(3);
    }
    {
        gh::Row apRow(b);
        String ap = apOn ? String(AP_SSID) + "  " + WiFi.softAPIP().toString() : String("off");
        b.Label_("ap", ap).label(F("Access Point")).size(3);
        b.Label(WiFi.macAddress()).label(F("MAC")).size(3);
    }
}

static String fmt(float v, int digits = 2) {
    return String(v, digits);
}

static void buildImu(gh::Builder& b) {
    if (!imu.ok) {
        gh::Row r(b);
        b.Label(F("MPU-6050 not found")).label(F("IMU")).size(6);
        return;
    }
    {
        gh::Row accRow(b);
        b.Label_("ax", fmt(imu.ax)).label(F("Accel X, g")).size(2);
        b.Label_("ay", fmt(imu.ay)).label(F("Accel Y, g")).size(2);
        b.Label_("az", fmt(imu.az)).label(F("Accel Z, g")).size(2);
    }
    {
        gh::Row gyrRow(b);
        b.Label_("gx", fmt(imu.gx, 1)).label(F("Gyro X, deg/s")).size(2);
        b.Label_("gy", fmt(imu.gy, 1)).label(F("Gyro Y, deg/s")).size(2);
        b.Label_("gz", fmt(imu.gz, 1)).label(F("Gyro Z, deg/s")).size(2);
    }
    {
        gh::Row tRow(b);
        b.Label_("imutemp", fmt(imu.temp, 1)).label(F("IMU temp, C")).size(3);
    }
}

void build(gh::Builder& b) {
    bool forceSave = false;

    b.Menu(F("Dashboard;LEDs;CAN;Wi-Fi;IMU"));

    switch (b.menu()) {
        case 0: buildDashboard(b); break;
        case 1: buildLeds(b, forceSave); break;
        case 2: buildCan(b); break;
        case 3: buildWifi(b); break;
        case 4: buildImu(b); break;
    }

    // If something changed, trigger the update
    if (b.changed() || forceSave) {
        reinit(selectedStrip);
        savedData.can_setting = can_setting;
        for (int i = 0; i < NUM_STRIPS; i++) {
            savedData.stripSettings[i] = stripSettings[i];
        }
        savedData.numLEDsStrip1 = numLedsPerStrip[0];
        savedData.numLEDsStrip2 = numLedsPerStrip[1];
        savedData.numLEDsStrip3 = numLedsPerStrip[2];
        savedData.numLEDsStrip4 = numLedsPerStrip[3];
        savedData.numLEDsStrip5 = numLedsPerStrip[4];
        savedData.numLEDsStrip6 = numLedsPerStrip[5];
        strlcpy(savedData.wifiSsid, wifiSsid.c_str(), sizeof(savedData.wifiSsid));
        strlcpy(savedData.wifiPass, wifiPass.c_str(), sizeof(savedData.wifiPass));
        savedData.canMode = canMode;
        Serial.println("Data changed, saving to file...");
        fileData.update();
        hub.sendRefresh();
    }
}
