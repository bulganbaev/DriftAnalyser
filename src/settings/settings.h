#ifndef SETTINGS_H
#define SETTINGS_H

#include <Arduino.h>
#include "led_control/led_control.h"

#define NUM_PRESETS 3

struct DriveSettings {
    bool masterOn;        // global output switch
    int shiftRPM;         // blink above this RPM (0 = use maxRPM)
    uint32_t shiftColor;
    int engineOff;        // when no data / rpm 0: 0 keep, 1 dim, 2 off
    int engineOffDim;     // brightness % used for engineOff == 1
    int powerLimitMa;     // FastLED power cap at 5V, 0 = off
    int lateralAxis;      // 0 +X, 1 -X, 2 +Y, 3 -Y, 4 +Z, 5 -Z
    int yawAxis;          // same encoding, gyro axis for yaw rate
    float maxLateralG;    // full scale for lateral G source
    float maxYawRate;     // deg/s full scale for yaw source
    float accOff[3];      // calibration offsets
    float gyrOff[3];
};

struct Preset {
    bool used;
    char name[17];
    StripSettings strips[NUM_STRIPS];
    int numLeds[NUM_STRIPS];
    CanSettings can;
};

struct SavedData {
    CanSettings can_setting;
    StripSettings stripSettings[NUM_STRIPS];
    int numLeds[NUM_STRIPS];
    char wifiSsid[33];
    char wifiPass[65];
    int canMode;
    DriveSettings drive;
    Preset presets[NUM_PRESETS];
};

extern SavedData savedData;
extern DriveSettings& drive;

void settingsBegin();       // mount FS, load file, push into live globals
void settingsSave();        // live globals -> savedData, schedule write
void settingsSaveNow();
void settingsTick();
void settingsPresetSave(int i);
bool settingsPresetLoad(int i);
String settingsPresetName(int i);

#endif
