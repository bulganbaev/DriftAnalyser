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

void rpmLevel(int stripIndex) {
    int level = obd2.getRPM();  // Получение текущего значения RPM от OBD2

    fill_solid(leds[stripIndex], numLEDsPerStrip[stripIndex], CRGB::Black); // Очищаем светодиоды

    int MIN_LEVEL = can_setting.minRPM;
    int MAX_LEVEL = can_setting.maxRPM;

    // Вычисляем количество светодиодов, которые нужно зажечь, на основе уровня RPM
    int numLedsToLight = map(level, MIN_LEVEL, MAX_LEVEL, 0, numLEDsPerStrip[stripIndex]);

    // Определяем точки перехода цветов
    int firstTransitionPoint = numLedsToLight * 0.1;  // Переход от синего к зеленому
    int secondTransitionPoint = numLedsToLight * 0.2; // Переход от зеленого к желтому
    int thirdTransitionPoint = numLedsToLight * 0.3;  // Переход от желтого к оранжевому
    int fourthTransitionPoint = numLedsToLight * 0.5; // Переход от оранжевого к красному
    int fifthTransitionPoint = numLedsToLight * 0.7;  // Переход от красного к пурпурному
    int sixthTransitionPoint = numLedsToLight * 0.9;  // Переход от пурпурного к белому

    // Запускаем анимацию на основе уровня RPM
    for (int i = 0; i < numLedsToLight; i++) {
        // Вычисляем индекс текущего светодиода
        int ledIndex = i;

        // Инициализируем параметры смешивания и начальные/конечные цвета
        float blendFactor = 0;
        CRGB startColor;
        CRGB endColor;

        if (i <= firstTransitionPoint) {
            // Переход от синего к зеленому
            blendFactor = float(i) / firstTransitionPoint;
            startColor = CRGB::Blue;
            endColor = CRGB::Green;
        } else if (i <= secondTransitionPoint) {
            // Переход от зеленого к желтому
            blendFactor = float(i - firstTransitionPoint) / (secondTransitionPoint - firstTransitionPoint);
            startColor = CRGB::Green;
            endColor = CRGB::Yellow;
        } else if (i <= thirdTransitionPoint) {
            // Переход от желтого к оранжевому
            blendFactor = float(i - secondTransitionPoint) / (thirdTransitionPoint - secondTransitionPoint);
            startColor = CRGB::Yellow;
            endColor = CRGB::Orange;
        } else if (i <= fourthTransitionPoint) {
            // Переход от оранжевого к красному
            blendFactor = float(i - thirdTransitionPoint) / (fourthTransitionPoint - thirdTransitionPoint);
            startColor = CRGB::Orange;
            endColor = CRGB::Red;
        } else if (i <= fifthTransitionPoint) {
            // Переход от красного к пурпурному
            blendFactor = float(i - fourthTransitionPoint) / (fifthTransitionPoint - fourthTransitionPoint);
            startColor = CRGB::Red;
            endColor = CRGB::Purple;
        } else if (i <= sixthTransitionPoint) {
            // Переход от пурпурного к розовому
            blendFactor = float(i - fifthTransitionPoint) / (sixthTransitionPoint - fifthTransitionPoint);
            startColor = CRGB::Purple;
            endColor = CRGB::Pink;
        } else {
            // Переход от розового к белому
            blendFactor = float(i - sixthTransitionPoint) / (numLedsToLight - sixthTransitionPoint);
            startColor = CRGB::Pink;
            endColor = CRGB::White;
        }

        // Смешивание цветов на основе коэффициента смешивания
        CRGB color = blend(startColor, endColor, uint8_t(blendFactor * 255));
        leds[stripIndex][ledIndex] = color; // Устанавливаем цвет для текущего светодиода
    }

    FastLED.setBrightness(mapBrightness(stripSettings[stripIndex].brightness)); // Устанавливаем яркость
    FastLED.show(); // Отображаем изменения
}



void runAnimations() {
    for (int i = 0; i < NUM_STRIPS; i++) {
        // Determine the current animation to use based on the mode
        bool useRpmLevel = (stripSettings[i].mode == 2) || 
                           (stripSettings[i].mode == 3 && obd2.getRPM() >= can_setting.minRPM);

        if (useRpmLevel) {
            // Use RPM-based animation
            rpmLevel(i);
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
