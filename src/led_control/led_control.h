#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <FastLED.h>
#include "config/config.h"
#include "pins/pins.h"

// Declare the LED strip and animation control functions

// Function to initialize the LED strips
void initializeLEDStrips();

// Different animation types for LED strips
void showStaticColor(int stripIndex, CRGB color);
void blinkAnimation(int stripIndex, CRGB color);
void rainbowAnimation(int stripIndex);
void fadeAnimation(int stripIndex, CRGB color);

// Function to run different animations for each strip
void runAnimations();

#endif
