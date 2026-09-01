#include "vehicle.h"

VehicleData vehicle;
int canMode = CAN_MODE_OBD2;

static CANBus* canBus = nullptr;
static OBD2* obd2p = nullptr;

static unsigned long lastObdPoll = 0;
const unsigned long OBD_POLL_INTERVAL = 200;

// frames/sec counter
static unsigned long frameCount = 0;
static unsigned long framesPerSec = 0;
static unsigned long lastRateTick = 0;
static unsigned long lastFrameMillis = 0;

// sniffer: per-ID throttled print
struct SniffEntry {
    uint32_t id;
    uint32_t count;
    unsigned long lastPrint;
};
const int SNIFF_MAX = 64;
static SniffEntry sniff[SNIFF_MAX];
static int sniffUsed = 0;
const unsigned long SNIFF_PRINT_INTERVAL = 500;

void vehicleSetup(CANBus& can, OBD2& obd) {
    canBus = &can;
    obd2p = &obd;
}

void vehicleSetMode(int mode) {
    canMode = mode;
    sniffUsed = 0;
    if (canBus) canBus->restart(mode != CAN_MODE_OBD2);
    Serial.print("CAN mode: ");
    Serial.println(mode == CAN_MODE_OBD2 ? "OBD2" : mode == CAN_MODE_BMW ? "BMW MS43" : "Sniffer");
}

// BMW E46 / MS43 PT-CAN, 500 kbit
static void decodeBmw(const twai_message_t& f) {
    switch (f.identifier) {
        case 0x316:  // DME1
            vehicle.rpm = ((f.data[3] << 8) | f.data[2]) / 6.4;
            vehicle.lastUpdate = millis();
            break;
        case 0x329:  // DME2
            vehicle.temp = f.data[1] * 0.75 - 48;
            vehicle.throttle = (uint16_t)f.data[5] * 100 / 254;
            vehicle.lastUpdate = millis();
            break;
        case 0x153:  // ASC1
            vehicle.speed = ((f.data[2] << 8) | f.data[1]) / 128;
            vehicle.lastUpdate = millis();
            break;
    }
}

static void sniffFrame(const twai_message_t& f) {
    unsigned long now = millis();
    SniffEntry* e = nullptr;
    for (int i = 0; i < sniffUsed; i++) {
        if (sniff[i].id == f.identifier) { e = &sniff[i]; break; }
    }
    if (!e) {
        if (sniffUsed >= SNIFF_MAX) return;
        e = &sniff[sniffUsed++];
        e->id = f.identifier;
        e->count = 0;
        e->lastPrint = 0;
    }
    e->count++;
    if (now - e->lastPrint < SNIFF_PRINT_INTERVAL) return;
    e->lastPrint = now;

    Serial.printf("%s%03X [%d]", f.extd ? "x" : " ", (unsigned)f.identifier, f.data_length_code);
    for (int i = 0; i < f.data_length_code; i++) Serial.printf(" %02X", f.data[i]);
    Serial.printf("  n=%lu\n", (unsigned long)e->count);
}

void vehicleTick() {
    unsigned long now = millis();
    if (now - lastRateTick >= 1000) {
        lastRateTick = now;
        framesPerSec = frameCount;
        frameCount = 0;
    }
    if (!canBus) return;

    if (canMode == CAN_MODE_OBD2) {
        if (now - lastObdPoll < OBD_POLL_INTERVAL) return;
        lastObdPoll = now;
        if (obd2p) obd2p->updateOBD2Data();
        return;
    }

    twai_message_t f;
    int budget = 64;  // frames per tick, keep the loop responsive
    while (budget-- > 0 && canBus->readFrame(f, 0)) {
        frameCount++;
        lastFrameMillis = now;
        if (canMode == CAN_MODE_BMW) decodeBmw(f);
        else sniffFrame(f);
    }
}

String canStatusString() {
    if (!canBus || !canBus->isDriverRunning()) return F("driver off");
    String s = canBus->stateName();
    if (canMode == CAN_MODE_OBD2) {
        unsigned long age = vehicle.lastUpdate ? (millis() - vehicle.lastUpdate) / 1000 : 0;
        s += vehicle.lastUpdate ? " ok " + String(age) + "s ago" : " no reply";
    } else {
        s += " " + String(framesPerSec) + " fps";
        if (lastFrameMillis) s += " last " + String((millis() - lastFrameMillis) / 1000) + "s";
    }
    return s;
}
