#include "settings.h"
#include <LittleFS.h>
#include <FileData.h>
#include "net/net.h"
#include "vehicle/vehicle.h"
#include "system/system.h"

SavedData savedData;
DriveSettings& drive = savedData.drive;

// key doubles as layout version: bump when SavedData changes
static FileData fileData(&LittleFS, "/settings.dat", 'B', &savedData, sizeof(savedData));
static bool writePending = false;
static unsigned long writeRequestedAt = 0;
const unsigned long WRITE_DELAY = 1500;  // coalesce bursts of changes

static void writeNow() {
    writePending = false;
    ledsPause();
    fileData.updateNow();
    ledsResume();
}

static void setDefaults() {
    memset(&savedData, 0, sizeof(savedData));
    savedData.can_setting = {2000, 7000, 100, 100};
    const int defaultLeds[NUM_STRIPS] = {276, 194, 94, 94, 94, 94};
    for (int i = 0; i < NUM_STRIPS; i++) {
        savedData.numLeds[i] = defaultLeds[i];
        savedData.stripSettings[i].enabled = true;
        savedData.stripSettings[i].color = 0xFF0000;
        savedData.stripSettings[i].brightness = 100;
    }
    strlcpy(savedData.wifiSsid, netDefaultSsid(), sizeof(savedData.wifiSsid));
    strlcpy(savedData.wifiPass, netDefaultPass(), sizeof(savedData.wifiPass));
    savedData.canMode = 0;
    DriveSettings& d = savedData.drive;
    d.masterOn = true;
    d.shiftRPM = 0;
    d.shiftColor = 0xFF0000;
    d.engineOff = 0;
    d.engineOffDim = 20;
    d.powerLimitMa = 0;
    d.lateralAxis = 2;   // +Y
    d.yawAxis = 4;       // +Z
    d.maxSpeed = 200;
    d.maxLateralG = 1.0f;
    d.maxYawRate = 60.0f;
    d.strip6Out = 0;
}

static void pushLive() {
    can_setting = savedData.can_setting;
    for (int i = 0; i < NUM_STRIPS; i++) {
        stripSettings[i] = savedData.stripSettings[i];
        numLedsPerStrip[i] = savedData.numLeds[i];
    }
    canMode = constrain(savedData.canMode, 0, 2);
    savedData.wifiSsid[sizeof(savedData.wifiSsid) - 1] = 0;
    savedData.wifiPass[sizeof(savedData.wifiPass) - 1] = 0;
    wifiSsid = savedData.wifiSsid;
    wifiPass = savedData.wifiPass;
}

static void pullLive() {
    savedData.can_setting = can_setting;
    for (int i = 0; i < NUM_STRIPS; i++) {
        savedData.stripSettings[i] = stripSettings[i];
        savedData.numLeds[i] = numLedsPerStrip[i];
    }
    savedData.canMode = canMode;
    strlcpy(savedData.wifiSsid, wifiSsid.c_str(), sizeof(savedData.wifiSsid));
    strlcpy(savedData.wifiPass, wifiPass.c_str(), sizeof(savedData.wifiPass));
}

void settingsBegin() {
    if (!LittleFS.begin()) {
        Serial.println("LittleFS mount failed, formatting");
        LittleFS.format();
        if (!LittleFS.begin()) {
            Serial.println("LittleFS unusable, running on defaults");
            setDefaults();
            pushLive();
            return;
        }
    }
    setDefaults();
    FDstat_t st = fileData.read();
    switch (st) {
        case FD_READ:  Serial.println("Settings loaded"); break;
        case FD_ADD:   Serial.println("Settings file created with defaults"); break;
        case FD_WRITE: Serial.println("Settings layout changed, defaults written"); break;
        default:       Serial.println("Settings read error, using defaults"); break;
    }
    pushLive();
}

void settingsSave() {
    pullLive();
    writePending = true;
    writeRequestedAt = millis();
}

void settingsSaveNow() {
    pullLive();
    writeNow();
}

void settingsTick() {
    if (writePending && millis() - writeRequestedAt >= WRITE_DELAY) writeNow();
}

void settingsPresetSave(int i) {
    if (i < 0 || i >= NUM_PRESETS) return;
    Preset& p = savedData.presets[i];
    p.used = true;
    if (!p.name[0]) snprintf(p.name, sizeof(p.name), "Preset %d", i + 1);
    for (int s = 0; s < NUM_STRIPS; s++) {
        p.strips[s] = stripSettings[s];
        p.numLeds[s] = numLedsPerStrip[s];
    }
    p.can = can_setting;
    settingsSave();
}

bool settingsPresetLoad(int i) {
    if (i < 0 || i >= NUM_PRESETS) return false;
    Preset& p = savedData.presets[i];
    if (!p.used) return false;
    for (int s = 0; s < NUM_STRIPS; s++) {
        stripSettings[s] = p.strips[s];
        numLedsPerStrip[s] = p.numLeds[s];
    }
    requestLedReinit();
    can_setting = p.can;
    settingsSave();
    return true;
}

String settingsPresetName(int i) {
    if (i < 0 || i >= NUM_PRESETS) return "";
    Preset& p = savedData.presets[i];
    if (!p.used) return "empty";
    return String(p.name);
}
