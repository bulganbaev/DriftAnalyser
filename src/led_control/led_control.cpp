#include "led_control.h"
// Define the LED pins and number of LEDs for each strip
const int ledPins[NUM_STRIPS] = {LED_PIN_1, LED_PIN_2, LED_PIN_3, LED_PIN_4, LED_PIN_5, LED_PIN_6};

// Array to store the CRGB arrays for each strip
CRGB* leds[NUM_STRIPS];

// Function to initialize the LED strips
void initializeLEDStrips() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        leds[i] = new CRGB[numLEDsPerStrip[i]];  // Allocate memory for each strip's LEDs

        // Debug message to check initialization
        Serial.print("Initializing strip ");
        Serial.print(i + 1);
        Serial.print(" with pin ");
        Serial.println(ledPins[i]);

        // Hard-code pin assignments at compile time by using a switch case
        switch (ledPins[i]) {
            case LED_PIN_1:
                FastLED.addLeds<WS2812B, LED_PIN_1, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            case LED_PIN_2:
                FastLED.addLeds<WS2812B, LED_PIN_2, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            case LED_PIN_3:
                FastLED.addLeds<WS2812B, LED_PIN_3, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            case LED_PIN_4:
                FastLED.addLeds<WS2812B, LED_PIN_4, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            case LED_PIN_5:
                FastLED.addLeds<WS2812B, LED_PIN_5, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            case LED_PIN_6:
                FastLED.addLeds<WS2812B, LED_PIN_6, RGB>(leds[i], numLEDsPerStrip[i]);
                break;
            default:
                // Handle error if an unsupported pin is passed (optional)
                Serial.println("Error: Unsupported pin!");
                break;
        }
    }
}

// Function for static color on a strip
void showStaticColor(int stripIndex, CRGB color) {
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = color;
    }
    FastLED.show();
}

// Blink animation for a strip
void blinkAnimation(int stripIndex, CRGB color) {
    static bool on = false;
    if (on) {
        showStaticColor(stripIndex, CRGB::Black);
    } else {
        showStaticColor(stripIndex, color);
    }
    on = !on;
}

// Rainbow animation for a strip
void rainbowAnimation(int stripIndex) {
    static uint8_t hue = 0;
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = CHSV(hue + (i * 10), 255, 255);
    }
    hue += 5;
    FastLED.show();
}

// Fade animation for a strip
void fadeAnimation(int stripIndex, CRGB color) {
    static uint8_t brightness = 0;
    static bool increasing = true;
    if (increasing) {
        brightness += 5;
        if (brightness >= 255) increasing = false;
    } else {
        brightness -= 5;
        if (brightness <= 0) increasing = true;
    }
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = color;
        leds[stripIndex][i].fadeToBlackBy(brightness);
    }
    FastLED.show();
}

// Function to run different animations for each strip
void runAnimations() {
    // // Example: different animations for each strip
    showStaticColor(0, CRGB::Red);          // Strip 1: Static red
    showStaticColor(1, CRGB::Green);         // Strip 2: Blinking green
    rainbowAnimation(2);                    // Strip 3: Rainbow
    fadeAnimation(3, CRGB::Blue);           // Strip 4: Fading blue
    rainbowAnimation(4);                    // Strip 5: Rainbow
    blinkAnimation(5, CRGB::Pink);          // Strip 6: Blinking pink
}