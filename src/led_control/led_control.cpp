#include "led_control.h"
#include "obd2/obd2.h"

// Define the LED pins array here (or in another shared header if needed)
const int ledPins[NUM_STRIPS] = {LED_PIN_1, LED_PIN_2, LED_PIN_3, LED_PIN_4, LED_PIN_5, LED_PIN_6};

// Use external variables from hub.cpp
CanSettings can_setting = {2000, 7000, 100, 100};  // Default CAN settings
StripSettings stripSettings[NUM_STRIPS] = {};      // Initialize with default values

int numLedsPerStrip[NUM_STRIPS] = {276, 194, 94, 94, 94, 94};
// Make the OBD2 object available
extern OBD2 obd2;

CRGB* leds[NUM_STRIPS];
CLEDController* controllers[NUM_STRIPS] = {};

// Per-strip animation state so strips don't share counters
struct AnimState {
    int pos = 0;
    int dir = 1;
    uint8_t phase = 0;
    int bright = 0;
    bool up = true;
    uint8_t heat[MAX_LEDS];
};
static AnimState anim[NUM_STRIPS];

// Helper function to convert `uint` color to CRGB
CRGB uintToCrgb(uint32_t color) {
    return CRGB((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF);
}

// Strips are registered as RGB; other orders are emulated by swapping
// channels in the buffer right before show() and restoring after.
static const uint8_t colorOrderMap[6][3] = {
    {0, 1, 2},  // RGB
    {1, 0, 2},  // GRB
    {2, 1, 0},  // BGR
    {0, 2, 1},  // RBG
    {1, 2, 0},  // GBR
    {2, 0, 1},  // BRG
};

static void applyColorOrder(int stripIndex, bool inverse) {
    int order = stripSettings[stripIndex].colorOrder;
    if (order <= 0 || order >= 6) return;
    const uint8_t* m = colorOrderMap[order];
    for (int i = 0; i < numLedsPerStrip[stripIndex]; i++) {
        CRGB src = leds[stripIndex][i];
        CRGB& dst = leds[stripIndex][i];
        if (!inverse) {
            dst[0] = src[m[0]];
            dst[1] = src[m[1]];
            dst[2] = src[m[2]];
        } else {
            dst[m[0]] = src[0];
            dst[m[1]] = src[1];
            dst[m[2]] = src[2];
        }
    }
}
void deinit(int index) {
    if (index >= 0 && index < NUM_STRIPS) {
        if (leds[index]) {
            delete[] leds[index];  // Deallocate memory for the specific strip
            leds[index] = nullptr;  // Set pointer to null to avoid dangling pointer
            Serial.print("Deinitialized strip ");
            Serial.println(index + 1);
        }
    } else {
        Serial.println("Invalid index for deinit");
    }
}

void init(int index) {
    if (numLedsPerStrip[index] < 1) numLedsPerStrip[index] = 1;
    if (numLedsPerStrip[index] > MAX_LEDS) numLedsPerStrip[index] = MAX_LEDS;
    if (controllers[index]) controllers[index]->setLeds(leds[index], numLedsPerStrip[index]);
    for (int i = numLedsPerStrip[index]; i < MAX_LEDS; i++) {
                leds[index][i] = CRGB::Black;  // Set LED to black
            }
}

void reinit(int index) {
    Serial.print("Reinitializing strip ");
    Serial.println(index + 1);

    // deinit(index);  // First, deinitialize the specific strip
    init(index);    // Then, initialize it again with the updated settings
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

    for (int i = 0; i < NUM_STRIPS; i++) {
        
        leds[i] = new CRGB[MAX_LEDS];  // Allocate new memory based on the updated numLEDsPerStrip

        // Debug message to check initialization
        Serial.print("Initializing strip ");
        Serial.print(i + 1);
        Serial.print(" with pin ");
        Serial.print(ledPins[i]);
        Serial.print(" and ");
        Serial.print(numLedsPerStrip[i]);
        Serial.println(" LEDs");

        // Initialize each strip with specific pin and WS2812B LED protocol
        switch (ledPins[i]) {
            case LED_PIN_1:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_1, RGB>(leds[i], numLedsPerStrip[i]);
                break;
            case LED_PIN_2:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_2, RGB>(leds[i], numLedsPerStrip[i]);
                break;
            case LED_PIN_3:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_3, RGB>(leds[i], numLedsPerStrip[i]);
                break;
            case LED_PIN_4:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_4, RGB>(leds[i], numLedsPerStrip[i]);
                break;
            case LED_PIN_5:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_5, RGB>(leds[i], numLedsPerStrip[i]);
                break;
            case LED_PIN_6:
                controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_6, RGB>(leds[i], numLedsPerStrip[i]);
                break;
        }
        init(i);

    }
}
// Speed 0-100 -> frame interval in ms
static int frameInterval(int speed) {
    return map(constrain(speed, 0, 100), 0, 100, 100, 1);
}

// Brightness 0-100 -> FastLED 0-255
static uint8_t mapBrightness(int brightness) {
    return map(constrain(brightness, 0, 100), 0, 100, 0, 255);
}

void staticColor(int s) {
    fill_solid(leds[s], numLedsPerStrip[s], uintToCrgb(stripSettings[s].color));
}

void theaterChase(int s) {
    int n = numLedsPerStrip[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    fill_solid(leds[s], n, CRGB::Black);
    for (int i = anim[s].pos; i < n; i += 3) leds[s][i] = color;
    anim[s].pos = (anim[s].pos + 1) % 3;
}

void snake(int s) {
    int n = numLedsPerStrip[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    const int len = 20;
    fill_solid(leds[s], n, CRGB::Black);
    for (int i = 0; i < len; i++) leds[s][(anim[s].pos + i) % n] = color;
    anim[s].pos = (anim[s].pos + 1) % n;
}

void colorWave(int s) {
    int n = numLedsPerStrip[s];
    const uint8_t waveLength = 20;
    for (int i = 0; i < n; i++) {
        leds[s][i] = CHSV(anim[s].phase + i * 255 / waveLength, 255, 255);
    }
    anim[s].phase += 5;
}

void breathingLight(int s) {
    int n = numLedsPerStrip[s];
    AnimState& st = anim[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    st.bright += st.up ? 5 : -5;
    if (st.bright >= 255) { st.bright = 255; st.up = false; }
    if (st.bright <= 0)   { st.bright = 0;   st.up = true; }
    for (int i = 0; i < n; i++) {
        leds[s][i] = color;
        leds[s][i].nscale8(st.bright);
    }
}

void rainbowCycle(int s) {
    int n = numLedsPerStrip[s];
    for (int i = 0; i < n; i++) {
        leds[s][i] = CHSV(anim[s].phase + i * 256 / n, 255, 255);
    }
    anim[s].phase += 1 + can_setting.speed / 12;
}

void meteorRain(int s) {
    int n = numLedsPerStrip[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    fadeToBlackBy(leds[s], n, 64);
    anim[s].pos %= n;
    leds[s][anim[s].pos] = color;
    anim[s].pos = (anim[s].pos + 1) % n;
}

void twinkle(int s) {
    int n = numLedsPerStrip[s];
    fadeToBlackBy(leds[s], n, 50);
    leds[s][random16(n)] = uintToCrgb(stripSettings[s].color);
}

void runningLights(int s) {
    int n = numLedsPerStrip[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    for (int i = 0; i < n; i++) {
        leds[s][i] = color;
        leds[s][i].nscale8(sin8(anim[s].phase + i * 16));
    }
    anim[s].phase++;
}

// Bouncing dot with a trail
void larsonScanner(int s) {
    int n = numLedsPerStrip[s];
    AnimState& st = anim[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    fadeToBlackBy(leds[s], n, 40);
    if (st.pos >= n) st.pos = n - 1;
    if (st.pos < 0) st.pos = 0;
    leds[s][st.pos] = color;
    st.pos += st.dir;
    if (st.pos >= n - 1) { st.pos = n - 1; st.dir = -1; }
    if (st.pos <= 0)     { st.pos = 0;     st.dir = 1; }
}

// Fire2012 by Mark Kriegsman
void fire(int s) {
    int n = numLedsPerStrip[s];
    uint8_t* heat = anim[s].heat;
    const uint8_t cooling = 55;
    const uint8_t sparking = 120;
    for (int i = 0; i < n; i++) {
        heat[i] = qsub8(heat[i], random8(0, ((cooling * 10) / n) + 2));
    }
    for (int k = n - 1; k >= 2; k--) {
        heat[k] = (heat[k - 1] + heat[k - 2] + heat[k - 2]) / 3;
    }
    if (random8() < sparking) {
        int y = random8(min(n, 7));
        heat[y] = qadd8(heat[y], random8(160, 255));
    }
    for (int j = 0; j < n; j++) leds[s][j] = HeatColor(heat[j]);
}

// Red / blue alternating halves
void police(int s) {
    int n = numLedsPerStrip[s];
    int period = map(constrain(can_setting.speed, 0, 100), 0, 100, 500, 60);
    bool phase = (millis() / period) & 1;
    int half = n / 2;
    fill_solid(leds[s], half, phase ? CRGB::Red : CRGB::Black);
    fill_solid(leds[s] + half, n - half, phase ? CRGB::Black : CRGB::Blue);
}

void confetti(int s) {
    int n = numLedsPerStrip[s];
    fadeToBlackBy(leds[s], n, 10);
    leds[s][random16(n)] += CHSV(anim[s].phase + random8(64), 200, 255);
    anim[s].phase++;
}

// Fill with color from the start, then wipe back to black
void colorWipe(int s) {
    int n = numLedsPerStrip[s];
    AnimState& st = anim[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    st.pos %= 2 * n;
    if (st.pos < n) leds[s][st.pos] = color;
    else            leds[s][st.pos - n] = CRGB::Black;
    st.pos = (st.pos + 1) % (2 * n);
}

// Smooth pendulum dot
void sinelon(int s) {
    int n = numLedsPerStrip[s];
    CRGB color = uintToCrgb(stripSettings[s].color);
    fadeToBlackBy(leds[s], n, 20);
    uint8_t bpm = map(constrain(can_setting.speed, 0, 100), 0, 100, 5, 60);
    int p = beatsin16(bpm, 0, n - 1);
    leds[s][p] += color;
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
    int numLeds = numLedsPerStrip[stripIndex];
    bool bottom = stripSettings[stripIndex].bottom;
    int center = stripSettings[stripIndex].center;

    int MIN_LEVEL = can_setting.minRPM;
    int MAX_LEVEL = can_setting.maxRPM;

    // Shift light: over max RPM the whole strip blinks red
    if (level >= MAX_LEVEL) {
        bool on = (millis() / 100) & 1;
        fill_solid(leds[stripIndex], numLeds, on ? CRGB::Red : CRGB::Black);
        return;
    }

    fill_solid(leds[stripIndex], numLeds, CRGB::Black);

    int numLedsToLight = map(level, MIN_LEVEL, MAX_LEVEL, 0, bottom ? numLedsPerStrip[stripIndex] / 2 - 1 : numLedsPerStrip[stripIndex]);

    if (bottom) {
        int midPoint =  center/ 2;  // Midpoint of the front strip
        for (int i = 0; i < numLedsToLight; i++) {
            CRGB currentColor = getColorForSection(i, numLeds / 2);
            leds[stripIndex][midPoint + i] = currentColor;
            int mirroredIndex = 2 * midPoint - i - 1;
            if (mirroredIndex >= 0) {
                leds[stripIndex][mirroredIndex] = currentColor;
            } else {
                leds[stripIndex][numLedsPerStrip[stripIndex] + mirroredIndex] = currentColor;
            }
        }
    } else {
        for (int i = 0; i < numLedsToLight; i++) {
            leds[stripIndex][i] = getColorForSection(i, numLeds);
        }
    }

}

void runAnimations() {
    static unsigned long lastFrame = 0;
    unsigned long now = millis();
    if (now - lastFrame < (unsigned long)frameInterval(can_setting.speed)) return;
    lastFrame = now;

    for (int i = 0; i < NUM_STRIPS; i++) {
        bool useRpmLevel = (stripSettings[i].mode == 1) ||
                           (stripSettings[i].mode == 2 && obd2.getRPM() >= can_setting.minRPM);

        if (useRpmLevel) {
            rpmLevel(i);
            continue;
        }
        switch (stripSettings[i].animationIndex) {
            case 0:  staticColor(i); break;
            case 1:  theaterChase(i); break;
            case 2:  colorWave(i); break;
            case 3:  breathingLight(i); break;
            case 4:  rainbowCycle(i); break;
            case 5:  snake(i); break;
            case 6:  meteorRain(i); break;
            case 7:  twinkle(i); break;
            case 8:  runningLights(i); break;
            case 9:  larsonScanner(i); break;
            case 10: fire(i); break;
            case 11: police(i); break;
            case 12: confetti(i); break;
            case 13: colorWipe(i); break;
            case 14: sinelon(i); break;
            default: break;
        }
    }
    FastLED.setBrightness(mapBrightness(can_setting.brightess));
    for (int i = 0; i < NUM_STRIPS; i++) applyColorOrder(i, false);
    FastLED.show();
    for (int i = 0; i < NUM_STRIPS; i++) applyColorOrder(i, true);
}
