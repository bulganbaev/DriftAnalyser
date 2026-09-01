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
    int colorOrder;          // 0 RGB, 1 GRB, 2 BGR, 3 RBG, 4 GBR, 5 BRG
    bool enabled;            // strip output on/off
    int scaleSource;         // 0 RPM, 1 speed, 2 throttle, 3 lateral G, 4 yaw rate
    bool reverse;            // flip direction
};

#define MAX_LEDS 1000

extern CanSettings can_setting;
extern StripSettings stripSettings[NUM_STRIPS];
// Extern LED and side settings
extern int numLedsPerStrip[6];

// Function to initialize the LED strips
void initializeLEDStrips();
void init(int index);    // apply numLedsPerStrip[index] to FastLED, blank the tail

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
void larsonScanner(int stripIndex);
void fire(int stripIndex);
void police(int stripIndex);
void confetti(int stripIndex);
void colorWipe(int stripIndex);
void sinelon(int stripIndex);
void gForce(int stripIndex);

// RPM-based animation
void rpmLevel(int stripIndex);

// Function to run the animations
void runAnimations();

#endif // LED_CONTROL_H
