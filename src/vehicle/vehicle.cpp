#include "vehicle.h"
#include "system/system.h"

VehicleData vehicle;
int canMode = CAN_MODE_OBD2;
int canBitrateSel = 0;

// auto bitrate scan (listen-only modes only)
static bool brLocked = false;
static unsigned long brWindowStart = 0;
static unsigned long brWindowFrames = 0;
static unsigned long brWindowErrStart = 0;
const unsigned long BR_WINDOW = 2500;

static CANBus* canBus = nullptr;
static OBD2* obd2p = nullptr;

const unsigned long DATA_STALE = 3000;  // ms without data -> values drop to 0

// frames/sec counter
static unsigned long frameCount = 0;
static unsigned long framesPerSec = 0;
static unsigned long lastRateTick = 0;
static unsigned long lastFrameMillis = 0;

// sniffer: per-ID throttled print
struct SniffEntry {
    uint32_t id;
    uint32_t count;
    uint32_t rate;        // frames in the last full second
    uint32_t rateCount;   // frames in the current second
    uint8_t dlc;
    uint8_t data[8];
    bool extd;
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

void vehicleSetBitrate(int sel) {
    canBitrateSel = constrain(sel, 0, BR_COUNT);
    brLocked = false;
    brWindowStart = millis();
    brWindowFrames = 0;
    if (!canBus) return;
    int idx = canBitrateSel ? canBitrateSel - 1 : BR_500K;
    canBus->restart(canMode != CAN_MODE_OBD2, idx);
    brWindowErrStart = canBus->busErrors();
}

String canBitrateString() {
    if (!canBus) return "?";
    String s = CANBus::bitrateName(canBus->bitrate());
    if (canBitrateSel == 0) s += brLocked ? " (auto, locked)" : " (auto, scanning)";
    return s;
}

static void bitrateScanTick(unsigned long now) {
    if (canBitrateSel != 0 || canMode == CAN_MODE_OBD2 || !canBus) return;
    if (now - brWindowStart < BR_WINDOW) return;
    unsigned long errs = canBus->busErrors() - brWindowErrStart;
    if (brWindowFrames > 0) {
        if (!brLocked) {
            brLocked = true;
            sysLog(String("CAN bitrate detected: ") + CANBus::bitrateName(canBus->bitrate()));
        }
    } else if (brLocked) {
        // frames stopped: keep the rate unless the bus is clearly wrong
        if (errs > 100) { brLocked = false; sysLog(F("CAN bitrate lost, rescanning")); }
    } else {
        int next = (canBus->bitrate() + 1) % BR_COUNT;
        canBus->restart(true, next);
        Serial.printf("CAN auto: %lu errors, trying %s\n", errs, CANBus::bitrateName(next));
    }
    brWindowStart = now;
    brWindowFrames = 0;
    brWindowErrStart = canBus->busErrors();
}

void vehicleSetMode(int mode) {
    canMode = mode;
    sniffUsed = 0;
    brLocked = false;
    brWindowStart = millis();
    brWindowFrames = 0;
    if (canBus) {
        int idx = canBitrateSel ? canBitrateSel - 1 : BR_500K;
        canBus->restart(mode != CAN_MODE_OBD2, idx);
        brWindowErrStart = canBus->busErrors();
    }
    sysLog(String("CAN mode: ") + (mode == CAN_MODE_OBD2 ? "OBD2" : mode == CAN_MODE_BMW ? "BMW MS43" : "Sniffer"));
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
        e->rate = 0;
        e->rateCount = 0;
        e->lastPrint = 0;
    }
    e->count++;
    e->rateCount++;
    e->dlc = f.data_length_code;
    e->extd = f.extd;
    memcpy(e->data, f.data, 8);
    if (now - e->lastPrint < SNIFF_PRINT_INTERVAL) return;
    e->lastPrint = now;

    Serial.printf("%s%03X [%d]", f.extd ? "x" : " ", (unsigned)f.identifier, f.data_length_code);
    for (int i = 0; i < f.data_length_code; i++) Serial.printf(" %02X", f.data[i]);
    Serial.printf("  n=%lu\n", (unsigned long)e->count);
}

void vehicleTick() {
    unsigned long now = millis();
    static unsigned long lastDiag = 0;
    if (canBus && canMode != CAN_MODE_OBD2 && now - lastDiag >= 5000) {
        lastDiag = now;
        Serial.println("CAN " + canBus->diagString() + " fps=" + String(framesPerSec));
    }
    if (now - lastRateTick >= 1000) {
        lastRateTick = now;
        framesPerSec = frameCount;
        frameCount = 0;
        for (int i = 0; i < sniffUsed; i++) {
            sniff[i].rate = sniff[i].rateCount;
            sniff[i].rateCount = 0;
        }
    }
    if (!canBus) return;

    // no fresh data: don't keep showing the last RPM forever
    if (vehicle.lastUpdate && now - vehicle.lastUpdate > DATA_STALE) {
        vehicle.rpm = 0;
        vehicle.speed = 0;
        vehicle.throttle = 0;
    }

    if (canMode == CAN_MODE_OBD2) {
        if (obd2p) obd2p->tick();
        return;
    }
    bitrateScanTick(now);

    twai_message_t f;
    int budget = 64;  // frames per tick, keep the loop responsive
    while (budget-- > 0 && canBus->readFrame(f, 0)) {
        frameCount++;
        brWindowFrames++;
        lastFrameMillis = now;
        if (canMode == CAN_MODE_BMW) decodeBmw(f);
        else sniffFrame(f);
    }
}

bool vehicleDataFresh() {
    return vehicle.lastUpdate && millis() - vehicle.lastUpdate <= DATA_STALE;
}

String canStatusString() {
    if (!canBus || !canBus->isDriverRunning()) return F("driver off");
    String s = canBus->stateName();
    if (canMode == CAN_MODE_OBD2) {
        if (!vehicle.lastUpdate) s += " no reply";
        else if (vehicleDataFresh()) s += " ok";
        else s += " stale " + String((millis() - vehicle.lastUpdate) / 1000) + "s";
    } else {
        s += " " + String(framesPerSec) + " fps";
        if (lastFrameMillis) s += " last " + String((millis() - lastFrameMillis) / 1000) + "s";
        twai_status_info_t st;
        if (twai_get_status_info(&st) == ESP_OK) s += " err=" + String((unsigned long)st.bus_error_count) + " rec=" + String((unsigned long)st.rx_error_counter);
    }
    return s;
}

// Sniffer table for the hub: one line per ID
String sniffTableString() {
    if (!sniffUsed) return F("no frames yet");
    String out;
    out.reserve(sniffUsed * 48);
    char line[64];
    for (int i = 0; i < sniffUsed; i++) {
        SniffEntry& e = sniff[i];
        int n = snprintf(line, sizeof(line), "%s%03X [%d]", e.extd ? "x" : "", (unsigned)e.id, e.dlc);
        for (int j = 0; j < e.dlc && j < 8; j++) n += snprintf(line + n, sizeof(line) - n, " %02X", e.data[j]);
        out += line;
        out += "  " + String(e.rate) + "/s n=" + String(e.count) + "\n";
    }
    return out;
}
