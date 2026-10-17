#include "ds2.h"
#include <string.h>

uint8_t ds2Checksum(const uint8_t* b, size_t n) {
    uint8_t x = 0;
    for (size_t i = 0; i < n; i++) x ^= b[i];
    return x;
}

size_t ds2Build(uint8_t addr, const uint8_t* body, size_t bodyLen, uint8_t* out, size_t cap) {
    size_t n = bodyLen + 3;
    if (n > cap || n > 255) return 0;
    out[0] = addr;
    out[1] = (uint8_t)n;
    memcpy(out + 2, body, bodyLen);
    out[n - 1] = ds2Checksum(out, n - 1);
    return n;
}

static int hexVal(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

size_t ds2ParseHex(const char* s, uint8_t* out, size_t cap) {
    size_t n = 0;
    int hi = -1;
    for (; *s; s++) {
        if (*s == ' ' || *s == ',') continue;
        int v = hexVal(*s);
        if (v < 0) return 0;
        if (hi < 0) {
            hi = v;
            continue;
        }
        if (n >= cap) return 0;
        out[n++] = (uint8_t)(hi << 4 | v);
        hi = -1;
    }
    return hi < 0 ? n : 0;
}

void Ds2Parser::start(const uint8_t* s, size_t n, uint8_t a) {
    sentLen = n > DS2_MAX_FRAME ? DS2_MAX_FRAME : n;
    if (sentLen) memcpy(sent, s, sentLen);
    echoPos = 0;
    addr = a;
    got = 0;
    want = 0;
}

Ds2Parser::Result Ds2Parser::feed(uint8_t b) {
    if (echoPos < sentLen) {
        if (b != sent[echoPos]) return BAD_ECHO;
        echoPos++;
        return MORE;
    }
    if (got == 0) {
        if (b != addr) return MORE;
        buf[got++] = b;
        return MORE;
    }
    if (got == 1) {
        if (b < 4 || b > DS2_MAX_FRAME) return BAD_LEN;
        want = b;
        buf[got++] = b;
        return MORE;
    }
    buf[got++] = b;
    if (got < want) return MORE;
    return ds2Checksum(buf, want - 1) == buf[want - 1] ? DONE : BAD_SUM;
}

static uint16_t be16(const uint8_t* p) {
    return (uint16_t)(p[0] << 8 | p[1]);
}

bool ms43DecodeStatus(const uint8_t* f, size_t len, Ms43Status& out) {
    if (len < 45 || f[0] != DS2_ADDR_MS43 || f[2] != 0xA0) return false;
    out.rpm = be16(f + 3);
    out.speed = f[5];
    out.pedalDeg = be16(f + 6) * 0.0018311f;
    out.throttleDeg = be16(f + 8) * 0.0018311f;
    out.intakeC = f[12] * 0.75f - 48.0f;
    out.coolantC = f[13] * 0.75f - 48.0f;
    out.vbat = f[43] * 0.10156f;
    return true;
}

uint8_t ms43PedalPercent(float deg) {
    float p = deg * 100.0f / MS43_PEDAL_FULL_DEG;
    if (p <= 0) return 0;
    if (p >= 100) return 100;
    return (uint8_t)(p + 0.5f);
}
