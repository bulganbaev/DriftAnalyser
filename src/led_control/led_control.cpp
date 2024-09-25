#include "led_control.h"
#include "obd2/obd2.h"

// Define the LED pins array here (or in another shared header if needed)
const int ledPins[NUM_STRIPS] = {LED_PIN_1, LED_PIN_2, LED_PIN_3, LED_PIN_4, LED_PIN_5, LED_PIN_6};

// Use external variables from hub.cpp
CanSettings can_setting = {2000, 7000, 100, 100};  // Default CAN settings
StripSettings stripSettings[NUM_STRIPS] = {};      // Initialize with default values

extern int numLEDsPerStrip[NUM_STRIPS];

// Make the OBD2 object available
extern OBD2 obd2;

CRGB* leds[NUM_STRIPS];

// Global variable for animation wave position
int wavePosition1 = 0;
int wavePosition2 = 0;

// Helper function to convert `uint` color to CRGB
CRGB uintToCrgb(uint32_t color) {
    return CRGB((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF);
}

// Function to deallocate the memory
void deinitializeLEDStrips() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        if (leds[i]) {
            delete[] leds[i];  // Deallocate memory for each strip
            leds[i] = nullptr;  // Set pointer to null to avoid dangling pointer
        }
    }
}

// Function to initialize/reinitialize the LED strips
void initializeLEDStrips() {
    deinitializeLEDStrips();  // Deallocate previous memory

    for (int i = 0; i < NUM_STRIPS; i++) {
        leds[i] = new CRGB[numLEDsPerStrip[i]];  // Allocate new memory based on the updated numLEDsPerStrip

        // Debug message to check initialization
        Serial.print("Initializing strip ");
        Serial.print(i + 1);
        Serial.print(" with pin ");
        Serial.print(ledPins[i]);
        Serial.print(" and ");
        Serial.print(numLEDsPerStrip[i]);
        Serial.println(" LEDs");

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
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = color;
    }
}

void theaterChase(int stripIndex) {
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);

    fill_solid(leds[stripIndex], numLEDsPerStrip[stripIndex], CRGB::Black);

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i += 3) {
        leds[stripIndex][(i + wavePosition1) % numLEDsPerStrip[stripIndex]] = color;
    }

    wavePosition1 = (wavePosition1 + 1) % numLEDsPerStrip[stripIndex];
}

void snake(int stripIndex) {
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);  // Get the current color for the strip

    int snakeLength = 20;  // Length of the chase "snake"
    
    // Clear the strip before updating
    fill_solid(leds[stripIndex], numLEDsPerStrip[stripIndex], CRGB::Black);

    // Update the LEDs for the theater chase effect
    for (int i = 0; i < snakeLength; i++) {
        int ledIndex = (i + wavePosition2) % numLEDsPerStrip[stripIndex];
        leds[stripIndex][ledIndex] = color;  // Set the current segment of the chase
    }

    // Move the wave position to create   the chase effect
    wavePosition2 = (wavePosition2 + 2 * snakeLength / 3) % numLEDsPerStrip[stripIndex];

}

void colorWave(int stripIndex) {
    static uint8_t startIndex = 0;  // Track the starting point of the wave
    
    // Speed and brightness adjustments

    // Create a gradient color wave that moves across the strip
    uint8_t waveLength = 20;  // Adjust the length of each color wave
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        uint8_t colorIndex = (startIndex + i * 255 / waveLength) % 255;  // Calculate color index for each LED
        leds[stripIndex][i] = CHSV(colorIndex, 255, 255);  // Use HSV for smooth color transitions
    }

    startIndex += 5;  // Increment startIndex to move the wave forward
}


void breathingLight(int stripIndex) {
    static int brightness = 0;
    static bool increasing = true;
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);

    if (increasing) {
        brightness += 5;
        if (brightness >= can_setting.brightess) {
            increasing = false;
        }
    } else {
        brightness -= 5;
        if (brightness <= 0) {
            increasing = true;
        }
    }

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = color;
        leds[stripIndex][i].fadeLightBy(255 - brightness);
    }
}

void rainbowCycle(int stripIndex) {
    static uint8_t hue = 0;

    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i] = CHSV(hue + (i * 256 / numLEDsPerStrip[stripIndex]), 255, can_setting.brightess);
    }

    hue = (hue + map(can_setting.speed, 1, 100, 1, 10)) % 256;
}

void meteorRain(int stripIndex) {
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);
    static int meteorPos = 0;  // Track the position of the meteor
    
    // Fade the LEDs slightly
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i].fadeToBlackBy(64);  // Fades each pixel to simulate a trail
    }

    // Draw the meteor
    leds[stripIndex][meteorPos] = color;

    // Move the meteor forward
    meteorPos = (meteorPos + 1) % numLEDsPerStrip[stripIndex];
}
void twinkle(int stripIndex) {
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);
    
    // Randomly pick an LED to twinkle
    int randomLed = random(numLEDsPerStrip[stripIndex]);
    
    // Fade all LEDs slightly
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        leds[stripIndex][i].fadeToBlackBy(50);
    }
    
    // Random LED becomes bright
    leds[stripIndex][randomLed] = color;
}
void runningLights(int stripIndex) {
    CRGB color = uintToCrgb(stripSettings[stripIndex].color);
    static int position = 0;

    // Create a sine wave effect
    for (int i = 0; i < numLEDsPerStrip[stripIndex]; i++) {
        int brightness = 128 + sin8(position + i * 16);  // Sine wave brightness effect
        leds[stripIndex][i] = color;
        leds[stripIndex][i].fadeToBlackBy(255 - brightness);  // Apply the sine wave to the strip
    }
    
    position++;  // Move the wave forward
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

void rpmLevel(int stripIndex) {
    int level = obd2.getRPM();  // Get the current RPM level
    int numLeds = numLEDsPerStrip[stripIndex];
    bool bottom = stripSettings[stripIndex].bottom;
    int center = stripSettings[stripIndex].center;

    fill_solid(leds[stripIndex], numLeds, CRGB::Black);

    int MIN_LEVEL = can_setting.minRPM;
    int MAX_LEVEL = can_setting.maxRPM;

    int numLedsToLight = map(level, MIN_LEVEL, MAX_LEVEL, 0, bottom ? numLEDsPerStrip[stripIndex] / 2 - 1 : numLEDsPerStrip[stripIndex]);

    if (bottom) {
        int midPoint =  center/ 2;  // Midpoint of the front strip
        for (int i = 0; i < numLedsToLight; i++) {
            CRGB currentColor = getColorForSection(i, numLeds / 2);
            leds[stripIndex][midPoint + i] = currentColor;
            int mirroredIndex = 2 * midPoint - i - 1;
            if (mirroredIndex >= 0) {
                leds[stripIndex][mirroredIndex] = currentColor;
            } else {
                leds[stripIndex][numLEDsPerStrip[stripIndex] + mirroredIndex] = currentColor;
            }
        }
    } else {
        for (int i = 0; i < numLedsToLight; i++) {
            leds[stripIndex][i] = getColorForSection(i, numLeds);
        }
    }

}

void runAnimations() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        // Log the current strip number
       

        // Determine if the RPM-based animation should be used
        bool useRpmLevel = (stripSettings[i].mode == 1) || 
                           (stripSettings[i].mode == 2 && obd2.getRPM() >= can_setting.minRPM);

        if (useRpmLevel) {
            Serial.println("Using RPM-based animation");
            rpmLevel(i);
        } else {
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
                case 5:
                    snake(i);
                    break;
                case 6:
                    meteorRain(i);   // New meteor rain effect
                    break;
                case 7:
                    twinkle(i);      // New twinkle effect
                    break;
                case 8:
                    runningLights(i);  // New running lights effect
                    break;
                default:
                    break;
        
        }
        }
    }
    FastLED.show();
    FastLED.setBrightness(can_setting.brightess);
    delay(mapSpeed(can_setting.speed));
}




