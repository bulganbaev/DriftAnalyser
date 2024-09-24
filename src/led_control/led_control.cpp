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
    .minRPM = 2000,  // Default min RPM
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


CRGB getColorForSection(int currentLED, int numLeds) {
    // Define the section thresholds for 7 sections
    int section1 = numLeds * 0.142;  // 1/7 of the strip
    int section2 = numLeds * 0.285;  // 2/7 of the strip
    int section3 = numLeds * 0.428;  // 3/7 of the strip
    int section4 = numLeds * 0.571;  // 4/7 of the strip
    int section5 = numLeds * 0.714;  // 5/7 of the strip
    int section6 = numLeds * 0.857;  // 6/7 of the strip

    // Return the color based on the section
    if (currentLED < section1) {
        return CRGB::Blue;        // First section, cold (low RPM)
    } else if (currentLED < section2) {
        return CRGB::Cyan;        // Second section, slightly higher, still cool
    } else if (currentLED < section3) {
        return CRGB::Green;       // Third section, moderate RPM, neutral
    } else if (currentLED < section4) {
        return CRGB::Yellow;      // Fourth section, starting to warm up
    } else if (currentLED < section5) {
        return CRGB::Orange;      // Fifth section, getting warmer
    } else if (currentLED < section6) {
        return CRGB::Red;         // Sixth section, hot, high RPM
    } else {
        return CRGB::Magenta;     // Last section, max RPM, very hot
    }
}


void rpmLevel(int stripIndex, bool bottom = false) {
    int level = obd2.getRPM();  // Get the current RPM level
    int numLeds = numLEDsPerStrip[stripIndex];
    // Clear LEDs
    fill_solid(leds[stripIndex], numLeds, CRGB::Black);

    int MIN_LEVEL = can_setting.minRPM;
    int MAX_LEVEL = can_setting.maxRPM;

    int numLedsToLight = map(level, MIN_LEVEL, MAX_LEVEL, 0, bottom ? numLEDsPerStrip[stripIndex] / 2 - 1 : numLEDsPerStrip[stripIndex]);

    

    if (bottom) {
        int midPoint = numLEDsPerSide[0] / 2;  // Midpoint of the front strip

        // Lighting from the middle outwards, mirroring for both sides
        for (int i = 0; i < numLedsToLight; i++) {
            // Calculate the current color based on the section
            CRGB currentColor = getColorForSection(i, numLeds/2);

            // Light the front side (from midpoint outwards)
            leds[stripIndex][midPoint + i] = currentColor;

            // Mirror the lighting for the other half
            int mirroredIndex = 2 * midPoint - i - 1;
            if (mirroredIndex >= 0) {
                leds[stripIndex][mirroredIndex] = currentColor;
            } else {
                leds[stripIndex][numLEDsPerStrip[stripIndex] + mirroredIndex] = currentColor;
            }
        }
    } else {
        // Standard mode: Light LEDs from start to numLedsToLight
        for (int i = 0; i < numLedsToLight; i++) {
            leds[stripIndex][i] = getColorForSection(i, numLeds);
        }
    }

    // Show the LEDs
    FastLED.show();
}







void runAnimations() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        // Determine the current animation to use based on the mode
        bool useRpmLevel = (stripSettings[i].mode == 2) || 
                           (stripSettings[i].mode == 3 && obd2.getRPM() >= can_setting.minRPM);

        if (useRpmLevel) {
            // Use RPM-based animation
            rpmLevel(i, false);
        } else {
            // Use regular animation based on animationIndex
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
        }
    }
}
