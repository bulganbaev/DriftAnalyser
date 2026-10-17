#pragma once
// BMW DS2 over K-line: [addr][len][data...][xor], len counts the whole frame.
// No Arduino deps, unit-tested on the host (test/test_ds2).
#include <stddef.h>
#include <stdint.h>

const uint8_t DS2_ADDR_MS43 = 0x12;
const size_t DS2_MAX_FRAME = 128;

uint8_t ds2Checksum(const uint8_t* b, size_t n);
// frame = addr, len, body..., xor; returns its length, 0 if it doesn't fit
size_t ds2Build(uint8_t addr, const uint8_t* body, size_t bodyLen, uint8_t* out, size_t cap);
// "12 05 0b 03" or "12050B03" -> bytes; 0 on bad char, odd digit count or overflow
size_t ds2ParseHex(const char* s, uint8_t* out, size_t cap);

// Byte-fed receiver. The K-line transceiver echoes our own request first, that echo
// is checked and dropped, then bytes before the expected address are skipped.
class Ds2Parser {
public:
    enum Result { MORE, DONE, BAD_ECHO, BAD_LEN, BAD_SUM };
    void start(const uint8_t* sent, size_t sentLen, uint8_t addr);
    Result feed(uint8_t b);
    const uint8_t* frame() const { return buf; }
    size_t length() const { return got; }

private:
    uint8_t sent[DS2_MAX_FRAME];
    size_t sentLen = 0;
    size_t echoPos = 0;
    uint8_t addr = 0;
    uint8_t buf[DS2_MAX_FRAME];
    size_t got = 0;
    size_t want = 0;
};

// MS43 reply to 12 05 0B 03, offsets from MS430DS0 SGBD table BETRIEBSWTAB.
// Not yet checked against a live car.
struct Ms43Status {
    uint16_t rpm = 0;
    uint8_t speed = 0;       // km/h
    float pedalDeg = 0;      // accelerator pedal, deg PWG
    float throttleDeg = 0;   // throttle plate, deg DK
    float intakeC = 0;
    float coolantC = 0;      // engine temperature
    float vbat = 0;
};

const uint8_t MS43_STATUS_REQ[] = {0x0B, 0x03};
const float MS43_PEDAL_FULL_DEG = 80.0f;  // pedal value at full travel, guess until seen in the car

bool ms43DecodeStatus(const uint8_t* f, size_t len, Ms43Status& out);
uint8_t ms43PedalPercent(float deg);
