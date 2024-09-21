#include "led_control.h"
#include "obd2/obd2.h"

// Define the LED pins and number of LEDs for each strip
const int ledPins[NUM_STRIPS] = {LED_PIN_1, LED_PIN_2, LED_PIN_3, LED_PIN_4, LED_PIN_5, LED_PIN_6};
CRGB* leds[NUM_STRIPS];

// Define settings for each strip
StripSettings stripSettings[NUM_STRIPS];

// Define the extern OBD2 instance
extern OBD2 obd2;

// Define global state for CAN settings
CanSettings can_setting = {
    .minRPM = 1000,  // Default min RPM
    .maxRPM = 7000   // Default max RPM
};

// Global variable for animation wave position
int wavePosition1 = 0;

void initializeLEDStrips() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        leds[i] = new CRGB[numLEDsPerStrip[i]];  // Allocate memory for each strip's LEDs

        // Debug message to check initialization
        Serial.print("Initializing strip ");
        Serial.print(i + 1);
        Serial.print(" with pin ");
        Serial.println(ledPins[i]);

        // Initialize each strip with specific pin and WS2812B LED protocol
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
        }

        // Default settings for each strip
        stripSettings[i].mode = 1;               // Default mode is non-RPM animation
        stripSettings[i].animationIndex = 0;     // Default animation is colorWave
        stripSettings[i].colorCount = 3;         // Default to 3 colors in colorSet
        stripSettings[i].colorSet[0] = CRGB::Red;
        stripSettings[i].colorSet[1] = CRGB::Green;
        stripSettings[i].colorSet[2] = CRGB::Blue;
        stripSettings[i].speed = 50;             // Default speed (0-100)
        stripSettings[i].brightness = 100;       // Default brightness (0-100)
    }
}

// Utility function to map speed from 0-100 to a usable delay
int mapSpeed(int speed) {
    return map(speed, 0, 100, 100, 1);  // Higher speed means shorter delay
}

// Utility function to map brightness from 0-100
int mapBrightness(int brightness) {
    return map(brightness, 0, 100, 0, 255);  // Map to FastLED brightness range
}

void staticColor(int stripIndex) {
    // Set the strip to the first color in the colorSet
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = stripSettings[stripIndex].colorSet[0];
    }
    FastLED.setBrightness(mapBrightness(stripSettings[stripIndex].brightness));
    FastLED.show();
}

void theaterChase(int stripIndex) {
    int delayTime = mapSpeed(stripSettings[stripIndex].speed);

    // Clear strip before updating
    fill_solid(leds[stripIndex], numLEDsPerStrip[stripIndex], CRGB::Black);

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i += 3) {
        leds[stripIndex][(i + wavePosition1) % numLEDsPerStrip[stripIndex]] = stripSettings[stripIndex].colorSet[0];
    }

    wavePosition1 = (wavePosition1 + 1) % numLEDsPerStrip[stripIndex];
    FastLED.setBrightness(mapBrightness(stripSettings[stripIndex].brightness));
    FastLED.show();
    delay(delayTime);
}

void colorWave(int stripIndex) {
    int ledsPerSection = numLEDsPerStrip[stripIndex] / stripSettings[stripIndex].colorCount;

    for (int i = 0; i < stripSettings[stripIndex].colorCount; i++) {
        for (int j = 0; j < ledsPerSection; j++) {
            int ledIndex = i * ledsPerSection + j;
            if (ledIndex < numLEDsPerStrip[stripIndex]) {
                leds[stripIndex][ledIndex] = stripSettings[stripIndex].colorSet[i];
            }
        }
    }
    FastLED.setBrightness(mapBrightness(stripSettings[stripIndex].brightness));
    FastLED.show();
    delay(mapSpeed(stripSettings[stripIndex].speed));
}

void breathingLight(int stripIndex) {
    static int brightness = 0;
    static bool increasing = true;

    if (increasing) {
        brightness += 5;
        if (brightness >= mapBrightness(stripSettings[stripIndex].brightness)) {
            increasing = false;
        }
    } else {
        brightness -= 5;
        if (brightness <= 0) {
            increasing = true;
        }
    }

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = stripSettings[stripIndex].colorSet[0];
        leds[stripIndex][i].fadeLightBy(255 - brightness);
    }
    FastLED.show();
    delay(mapSpeed(stripSettings[stripIndex].speed));
}

void rainbowCycle(int stripIndex) {
    static uint8_t hue = 0;

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = CHSV(hue + (i * 256 / numLEDsPerStrip[stripIndex]), 255, mapBrightness(stripSettings[stripIndex].brightness));
    }

    hue += 5;
    FastLED.show();
    delay(mapSpeed(stripSettings[stripIndex].speed));
}

void rpmLevel(int stripIndex) {
    int level = obd2.getRPM(); // Use actual RPM data from OBD2
    fill_solid(leds[stripIndex], numLEDsPerStrip[stripIndex], CRGB::Black); // Clear strip

    int numLedsToLight = map(level, can_setting.minRPM, can_setting.maxRPM, 0, numLEDsPerStrip[stripIndex]);

    for (int i = 0; i < numLedsToLight; i++) {
        leds[stripIndex][i] = CRGB::Red; 
    }
    FastLED.setBrightness(mapBrightness(stripSettings[stripIndex].brightness));
    FastLED.show();
}

void runAnimations() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        if (stripSettings[i].mode == 1) {
            switch (stripSettings[i].animationIndex) {
                case 0:
                    staticColor(i);
                    break;
                case 1:
                    theaterChase(i);
                    break;
                case 2:
                    colorWave(i);
                    break;
                case 3:
                    breathingLight(i);
                    break;
                case 4:
                    rainbowCycle(i);
                    break;
            }
        } else if (stripSettings[i].mode == 2) {
            rpmLevel(i);
        }
    }
}
