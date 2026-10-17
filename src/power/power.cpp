#include "power.h"
#include <power_latch.h>
#include "pins/pins.h"
#include "settings/settings.h"
#include "led_control/led_control.h"
#include "system/system.h"
#include "vehicle/vehicle.h"

PowerState power;

static PowerLatch latch;
static unsigned long lastTick = 0;
const unsigned long POWER_INTERVAL = 10;
const float SMOOTH = 0.1f;

static void setSwitch(bool on) {
    if (on == power.on) return;
    power.on = on;
    if (on) latch.reset();
    digitalWrite(LED_PWR_EN_PIN, on ? HIGH : LOW);
}

void powerBegin() {
    pinMode(LED_PWR_EN_PIN, OUTPUT);
    digitalWrite(LED_PWR_EN_PIN, LOW);
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, HIGH);
    analogReadResolution(12);
    analogSetPinAttenuation(VBAT_SENSE_PIN, ADC_11db);
    analogSetPinAttenuation(LED_ISENSE_PIN, ADC_6db);  // ~1.75 V full scale: ~84 A, better low end than 11 dB
    power.vbat = vbatFromAdc(analogReadMilliVolts(VBAT_SENSE_PIN) / 1000.0f);
}

void powerResetLatch() {
    if (!power.latched) return;
    power.latched = false;
    power.reason = "";
    sysLog(F("LED power latch reset"));
}

void powerTick() {
    unsigned long now = millis();
    if (now - lastTick < POWER_INTERVAL) return;
    lastTick = now;

    float vbat = vbatFromAdc(analogReadMilliVolts(VBAT_SENSE_PIN) / 1000.0f);
    power.isVolts = analogReadMilliVolts(LED_ISENSE_PIN) / 1000.0f;
    power.vbat += (vbat - power.vbat) * SMOOTH;
    float cal = constrain(savedData.currentCal, 0.3f, 3.0f);
    power.ledAmps += (isVoltsToAmps(power.isVolts) * cal - power.ledAmps) * SMOOTH;

    if (power.on) {
        PowerLatch::Trip t = latch.update(now, power.ledAmps, power.isVolts, drive.ledMaxAmps);
        if (t != PowerLatch::NONE) {
            power.latched = true;
            power.reason = t == PowerLatch::FAULT ? "switch fault, IS " + String(power.isVolts, 2) + " V"
                                                  : "overcurrent " + String(power.ledAmps, 1) + " A";
            setSwitch(false);
            sysLog("LED power off: " + power.reason);
        }
    }
    // first frame is black, so the strips never wake up on stale data
    bool parked = savedData.cutPowerEngineOff && drive.engineOff == 2 && !(vehicleDataFresh() && vehicle.rpm > 300);
    setSwitch(drive.masterOn && !power.latched && !parked && ledsFrameShown());

    // 1 Hz normal, 5 Hz latched
    digitalWrite(STATUS_LED_PIN, (now / (power.latched ? 100 : 500)) & 1);
}

String powerStatusString() {
    if (power.latched) return "OFF (latched): " + power.reason;
    return power.on ? F("on") : F("off");
}
