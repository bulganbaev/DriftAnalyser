#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <FastLED.h>
#include "config/config.h"
#include "pins/pins.h"


// Define a structure for CAN settings
struct CanSettings {
    int minRPM;
    int maxRPM;
};

// Define a structure for strip settings
struct StripSettings {
    int mode;                // Mode 1: Non-RPM, Mode 2: RPM-based
    int animationIndex;      // Index to choose the animation
    CRGB colorSet[10];       // Array of colors for non-RPM animations
    int colorCount;          // Number of colors in the colorSet
    int speed;               // Animation speed (0-100)
    int brightness;          // Brightness (0-100)
};

// Global variables for can_settings and wave position
extern CanSettings can_setting;
extern int wavePosition1;

// Array to store strip settings for each LED strip
extern StripSettings stripSettings[NUM_STRIPS];

// Function to initialize the LED strips
void initializeLEDStrips();

// Different animation types for LED strips
void staticColor(int stripIndex);
void theaterChase(int stripIndex);
void colorWave(int stripIndex);
void breathingLight(int stripIndex);
void rainbowCycle(int stripIndex);

// RPM-based animation
void rpmLevel(int stripIndex);

// Function to run the animations
void runAnimations();

#endif // LED_CONTROL_H
