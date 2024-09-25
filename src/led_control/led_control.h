#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <FastLED.h>
#include "config/config.h"
#include "pins/pins.h"

// Define a structure for CAN settings
struct CanSettings {
    int minRPM;
    int maxRPM;
    int speed;
    int brightess;
};

// Define a structure for strip settings
struct StripSettings {
    int mode;                // Mode 1: Non-RPM, Mode 2: RPM-based
    int animationIndex;      // Index to choose the animation
    uint32_t color;              // Single color for non-RPM animations
    int brightness;          // Brightness (0-100)
    bool bottom;             // Whether the strip is bottom or full length
    int center;
    int numLeds;
};

// Global variables for can_settings and wave position
extern int wavePosition1;

extern CanSettings can_setting;
extern StripSettings stripSettings[NUM_STRIPS];
// Extern LED and side settings
extern  int numLEDsPerStrip[NUM_STRIPS];  

// Function to initialize the LED strips
void initializeLEDStrips();

// Different animation types for LED strips
void staticColor(int stripIndex);
void theaterChase(int stripIndex);
void colorWave(int stripIndex);
void breathingLight(int stripIndex);
void rainbowCycle(int stripIndex);
void snake(int stripIndex);
void meteorRain(int stripIndex);
void twinkle(int stripIndex);
void runningLights(int stripIndex);

// RPM-based animation
void rpmLevel(int stripIndex);

// Function to run the animations
void runAnimations();

#endif // LED_CONTROL_H
