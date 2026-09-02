#include "obd2/obd2.h"
#include "vehicle/vehicle.h"
#include <Arduino.h>

static const uint8_t PIDS[] = {0x0C, 0x0D, 0x11, 0x05};  // rpm, speed, throttle, coolant
const unsigned long OBD_GAP = 50;       // ms between requests
const unsigned long OBD_TIMEOUT = 200;  // ms to wait for a reply

uint16_t OBD2::getRPM() const { return vehicle.rpm; }
uint8_t OBD2::getThrottlePosition() const { return vehicle.throttle; }
uint8_t OBD2::getSpeed() const { return vehicle.speed; }
int8_t OBD2::getEngineTemp() const { return vehicle.temp; }

void OBD2::begin(CANBus &can) {
    canBus = &can;
}

void OBD2::sendRequest(uint8_t pid) {
    twai_message_t tx = {};
    tx.identifier = 0x7DF;  // functional request to all ECUs
    tx.data_length_code = 8;
    tx.data[0] = 0x02;
    tx.data[1] = 0x01;  // mode 01: current data
    tx.data[2] = pid;
    canBus->sendFrame(tx);
}

bool OBD2::handleFrame(const twai_message_t &f, uint8_t pid) {
    if (f.identifier < 0x7E8 || f.identifier > 0x7EF) return false;
    if (f.data[1] != 0x41 || f.data[2] != pid) return false;
    switch (pid) {
        case 0x0C: vehicle.rpm = ((f.data[3] << 8) | f.data[4]) / 4; break;
        case 0x0D: vehicle.speed = f.data[3]; break;
        case 0x11: vehicle.throttle = (uint16_t)f.data[3] * 100 / 255; break;
        case 0x05: vehicle.temp = (int)f.data[3] - 40; break;
    }
    vehicle.lastUpdate = millis();
    return true;
}

void OBD2::tick() {
    if (!canBus || !canBus->isDriverRunning() || canBus->isListenOnly()) return;
    unsigned long now = millis();

    if (waiting) {
        twai_message_t f;
        int budget = 16;
        while (budget-- > 0 && canBus->readFrame(f, 0)) {
            if (handleFrame(f, PIDS[pidIndex])) {
                waiting = false;
                pidIndex = (pidIndex + 1) % sizeof(PIDS);
                return;
            }
        }
        if (now - sentAt >= OBD_TIMEOUT) {
            waiting = false;
            pidIndex = (pidIndex + 1) % sizeof(PIDS);
        }
        return;
    }

    if (now - lastSend < OBD_GAP) return;
    sendRequest(PIDS[pidIndex]);
    lastSend = sentAt = now;
    waiting = true;
}
