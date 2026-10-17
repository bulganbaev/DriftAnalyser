#include "led_control.h"
#include "obd2/obd2.h"
#include "settings/settings.h"
#include "vehicle/vehicle.h"
#include "imu/imu.h"

const int ledPins[NUM_STRIPS] = {LED_PIN_1, LED_PIN_2, LED_PIN_3, LED_PIN_4, LED_PIN_5, LED_PIN_6};

CanSettings can_setting = {2000, 7000, 100, 100};
StripSettings stripSettings[NUM_STRIPS] = {};
int numLedsPerStrip[NUM_STRIPS] = {276, 194, 94, 94, 94, 94};

extern OBD2 obd2;

// Animations render into leds[], the transformed copy in out[] is what FastLED sends
CRGB* leds[NUM_STRIPS];
static CRGB* out[NUM_STRIPS];
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

CRGB uintToCrgb(uint32_t color) {
    return CRGB((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF);
}

// 0 RGB, 1 GRB, 2 BGR, 3 RBG, 4 GBR, 5 BRG
static const uint8_t colorOrderMap[6][3] = {
    {0, 1, 2}, {1, 0, 2}, {2, 1, 0}, {0, 2, 1}, {1, 2, 0}, {2, 0, 1},
};

void init(int index) {
    if (numLedsPerStrip[index] < 1) numLedsPerStrip[index] = 1;
    if (numLedsPerStrip[index] > MAX_LEDS) numLedsPerStrip[index] = MAX_LEDS;
    if (controllers[index]) controllers[index]->setLeds(out[index], numLedsPerStrip[index]);
    for (int i = numLedsPerStrip[index]; i < MAX_LEDS; i++) leds[index][i] = CRGB::Black;
}

void initializeLEDStrips() {
    FastLED.setDither(0);  // temporal dither shows as flicker at low frame rates
    for (int i = 0; i < NUM_STRIPS; i++) {
        leds[i] = new CRGB[MAX_LEDS];
        out[i] = new CRGB[MAX_LEDS];
        fill_solid(leds[i], MAX_LEDS, CRGB::Black);
        fill_solid(out[i], MAX_LEDS, CRGB::Black);

        Serial.printf("Initializing strip %d with pin %d and %d LEDs\n", i + 1, ledPins[i], numLedsPerStrip[i]);
        switch (ledPins[i]) {
            case LED_PIN_1: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_1, RGB>(out[i], numLedsPerStrip[i]); break;
            case LED_PIN_2: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_2, RGB>(out[i], numLedsPerStrip[i]); break;
            case LED_PIN_3: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_3, RGB>(out[i], numLedsPerStrip[i]); break;
            case LED_PIN_4: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_4, RGB>(out[i], numLedsPerStrip[i]); break;
            case LED_PIN_5: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_5, RGB>(out[i], numLedsPerStrip[i]); break;
            case LED_PIN_6: controllers[i] = &FastLED.addLeds<WS2812B, LED_PIN_6, RGB>(out[i], numLedsPerStrip[i]); break;
        }
        init(i);
    }
}

// Speed 0-100 -> frame interval in ms. Floor at ~60 fps so Wi-Fi and the hub get loop time:
// pushing ~850 LEDs already takes ~25 ms per frame.
static int frameInterval(int speed) {
    return map(constrain(speed, 0, 100), 0, 100, 150, 16);
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

// Whole strip coloured by lateral G: blue one way, red the other, brightness by magnitude
void gForce(int s) {
    int n = numLedsPerStrip[s];
    float g = drive.maxLateralG > 0 ? imuLateralG() / drive.maxLateralG : 0;
    g = constrain(g, -1.0f, 1.0f);
    uint8_t v = (uint8_t)(fabsf(g) * 255);
    CRGB c = g < 0 ? CRGB(0, 0, 255) : CRGB(255, 0, 0);
    c.nscale8(max(v, (uint8_t)8));
    fill_solid(leds[s], n, c);
}

CRGB getColorForSection(int currentLED, int numLeds) {
    // 7 colour bands, cold to hot
    static const CRGB bands[7] = {CRGB::Blue, CRGB::Cyan, CRGB::Green, CRGB::Yellow, CRGB::Orange, CRGB::Red, CRGB::Magenta};
    if (numLeds < 1) numLeds = 1;
    int band = currentLED * 7 / numLeds;
    return bands[constrain(band, 0, 6)];
}

// Value of a scale source as fraction of full scale, signed for G / yaw
static float scaleFraction(int source) {
    switch (source) {
        case 1:  return drive.maxSpeed > 0 ? (float)vehicle.speed / drive.maxSpeed : 0;
        case 2:  return vehicle.throttle / 100.0f;
        case 3:  return drive.maxLateralG > 0 ? imuLateralG() / drive.maxLateralG : 0;
        case 4:  return drive.maxYawRate > 0 ? imuYawRate() / drive.maxYawRate : 0;
        default: {
            int span = can_setting.maxRPM - can_setting.minRPM;
            if (span <= 0) return 0;
            return (float)((int)vehicle.rpm - can_setting.minRPM) / span;
        }
    }
}

static bool shiftLightActive() {
    int threshold = drive.shiftRPM > 0 ? drive.shiftRPM : can_setting.maxRPM;
    return vehicleDataFresh() && (int)vehicle.rpm >= threshold;
}

// Bar graph driven by the selected source
void rpmLevel(int s) {
    int n = numLedsPerStrip[s];
    const StripSettings& st = stripSettings[s];

    if (st.scaleSource == 0 && shiftLightActive()) {
        bool on = (millis() / 100) & 1;
        fill_solid(leds[s], n, on ? uintToCrgb(drive.shiftColor) : CRGB::Black);
        return;
    }

    fill_solid(leds[s], n, CRGB::Black);
    float frac = scaleFraction(st.scaleSource);
    bool signedSource = st.scaleSource >= 3;

    if (st.bottom) {
        // grow from the middle LED outwards
        int mid = constrain(st.center, 0, n - 1);
        int half = max(mid, n - 1 - mid);
        if (signedSource) {
            // negative = left of middle, positive = right
            int len = constrain((int)(fabsf(frac) * half), 0, half);
            for (int i = 0; i < len; i++) {
                int idx = frac < 0 ? mid - i : mid + i;
                if (idx >= 0 && idx < n) leds[s][idx] = getColorForSection(i, half);
            }
        } else {
            int len = constrain((int)(frac * half), 0, half);
            for (int i = 0; i < len; i++) {
                CRGB c = getColorForSection(i, half);
                if (mid + i < n) leds[s][mid + i] = c;
                if (mid - i >= 0) leds[s][mid - i] = c;
            }
        }
    } else {
        int len = constrain((int)(fabsf(frac) * n), 0, n);
        for (int i = 0; i < len; i++) leds[s][i] = getColorForSection(i, n);
    }
}

static bool engineOn() {
    return vehicleDataFresh() && vehicle.rpm > 300;
}

static void renderStrip(int i) {
    const StripSettings& st = stripSettings[i];
    bool useScale = (st.mode == 1) || (st.mode == 2 && scaleFraction(st.scaleSource) > 0.05f);
    if (useScale) {
        rpmLevel(i);
        return;
    }
    switch (st.animationIndex) {
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
        case 15: gForce(i); break;
        default: staticColor(i); break;
    }
}

// leds[] -> out[]: enable, brightness, reverse, colour order
static void transformStrip(int i) {
    const StripSettings& st = stripSettings[i];
    int n = numLedsPerStrip[i];
    CRGB* dstBuf = out[i];
    if (!st.enabled) {
        fill_solid(dstBuf, n, CRGB::Black);
        return;
    }
    uint8_t scale = mapBrightness(st.brightness);
    int order = constrain(st.colorOrder, 0, 5);
    const uint8_t* m = colorOrderMap[order];
    for (int k = 0; k < n; k++) {
        CRGB src = leds[i][st.reverse ? n - 1 - k : k];
        src.nscale8(scale);
        CRGB& dst = dstBuf[k];
        dst[0] = src[m[0]];
        dst[1] = src[m[1]];
        dst[2] = src[m[2]];
    }
}

static volatile bool reinitPending = false;
static volatile bool frameShown = false;

bool ledsFrameShown() {
    return frameShown;
}

void requestLedReinit() {
    reinitPending = true;
}

void runAnimations() {
    static unsigned long lastFrame = 0;
    static int lastPowerLimit = -1;
    unsigned long now = millis();
    if (now - lastFrame < (unsigned long)frameInterval(can_setting.speed)) return;
    lastFrame = now;

    if (reinitPending) {
        reinitPending = false;
        for (int i = 0; i < NUM_STRIPS; i++) init(i);
    }

    if (drive.powerLimitMa != lastPowerLimit) {
        lastPowerLimit = drive.powerLimitMa;
        FastLED.setMaxPowerInVoltsAndMilliamps(12, drive.powerLimitMa > 0 ? drive.powerLimitMa : 100000);
    }

    int brightness = can_setting.brightess;
    bool blackout = !drive.masterOn || !frameShown;
    if (!blackout && !engineOn()) {
        if (drive.engineOff == 2) blackout = true;
        else if (drive.engineOff == 1) brightness = brightness * constrain(drive.engineOffDim, 0, 100) / 100;
    }

    for (int i = 0; i < NUM_STRIPS; i++) {
        if (blackout) {
            fill_solid(out[i], numLedsPerStrip[i], CRGB::Black);
            continue;
        }
        renderStrip(i);
        transformStrip(i);
    }
    FastLED.setBrightness(mapBrightness(brightness));
    FastLED.show();
    frameShown = true;
}

// Flash writes (settings, log, OTA) must not overlap RMT output. The LED task holds
// frameMutex for the whole frame; a writer takes it (blocking until the frame ends) and
// keeps it until resume, so no race window between check and show().
static SemaphoreHandle_t frameMutex = nullptr;
static volatile bool pausedFlag = false;

static void ensureMutex() {
    if (!frameMutex) frameMutex = xSemaphoreCreateMutex();
}

void ledsPause() {
    ensureMutex();
    if (pausedFlag) return;
    xSemaphoreTake(frameMutex, portMAX_DELAY);
    pausedFlag = true;
}

void ledsResume() {
    if (!pausedFlag) return;
    pausedFlag = false;
    xSemaphoreGive(frameMutex);
}

bool ledsPaused() {
    return pausedFlag;
}

static void ledTask(void*) {
    ensureMutex();
    for (;;) {
        xSemaphoreTake(frameMutex, portMAX_DELAY);
        runAnimations();
        xSemaphoreGive(frameMutex);
        vTaskDelay(1);
    }
}

void startLedTask() {
    ensureMutex();
    // same core as loop(): show() sleeps on the RMT semaphore, so the hub gets that time
    xTaskCreatePinnedToCore(ledTask, "leds", 6144, nullptr, 1, nullptr, 1);
}
