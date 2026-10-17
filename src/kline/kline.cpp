#include "kline.h"
#include <driver/gpio.h>
#include "pins/pins.h"
#include "vehicle/vehicle.h"

KlineStats klineStats;
Ms43Status ms43;

static HardwareSerial kSerial(1);
static Ds2Parser parser;
static uint8_t txBuf[DS2_MAX_FRAME];
static size_t txLen = 0;
static uint8_t lastFrame[DS2_MAX_FRAME];
static size_t lastLen = 0;

static uint8_t customBuf[DS2_MAX_FRAME];
static size_t customLen = 0;   // queued custom request, 0 = none
static bool customInFlight = false;
static String customReply = "-";

static bool waiting = false;
static unsigned long sentAt = 0;
static unsigned long nextAt = 0;
static uint32_t okThisSecond = 0;
static unsigned long secondStart = 0;

const unsigned long REPLY_TIMEOUT = 400;  // echo + 300 ms for the ECU
const unsigned long GAP = 10;             // between requests

static String hex(const uint8_t* b, size_t n) {
    String s;
    s.reserve(n * 3);
    char t[4];
    for (size_t i = 0; i < n; i++) {
        snprintf(t, sizeof(t), i ? " %02X" : "%02X", b[i]);
        s += t;
    }
    return s;
}

void klineBegin() {
    kSerial.begin(9600, SERIAL_8E1, K_RX_PIN, K_TX_PIN);
    gpio_pullup_en((gpio_num_t)K_RX_PIN);
}

bool klineSendCustom(const uint8_t* raw, size_t n) {
    if (n < 2 || n + 1 > DS2_MAX_FRAME) return false;
    memcpy(customBuf, raw, n);
    customBuf[n] = ds2Checksum(raw, n);
    customLen = n + 1;
    customReply = "pending";
    return true;
}

static void send() {
    while (kSerial.available()) kSerial.read();
    customInFlight = customLen > 0;
    if (customInFlight) {
        memcpy(txBuf, customBuf, customLen);
        txLen = customLen;
        customLen = 0;
    } else {
        txLen = ds2Build(DS2_ADDR_MS43, MS43_STATUS_REQ, sizeof(MS43_STATUS_REQ), txBuf, sizeof(txBuf));
    }
    parser.start(txBuf, txLen, txBuf[0]);
    kSerial.write(txBuf, txLen);
    klineStats.tx++;
    waiting = true;
    sentAt = millis();
}

static void finish(unsigned long now) {
    waiting = false;
    nextAt = now + GAP;
}

static void onFrame(const uint8_t* f, size_t n) {
    memcpy(lastFrame, f, n);
    lastLen = n;
    if (customInFlight) {
        customReply = hex(f, n);
        Serial.println("DS2 custom reply: " + customReply);
        return;
    }
    if (!ms43DecodeStatus(f, n, ms43)) {
        klineStats.nack++;
        return;
    }
    klineStats.ok++;
    okThisSecond++;
    vehicle.rpm = ms43.rpm;
    vehicle.speed = ms43.speed;
    vehicle.throttle = ms43PedalPercent(ms43.pedalDeg);
    vehicle.temp = (int8_t)lroundf(ms43.coolantC);
    vehicle.lastUpdate = millis();
}

void klineTick() {
    unsigned long now = millis();
    if (now - secondStart >= 1000) {
        secondStart = now;
        klineStats.hz = okThisSecond;
        okThisSecond = 0;
    }
    if (!waiting) {
        if ((long)(now - nextAt) >= 0) send();
        return;
    }
    while (kSerial.available()) {
        Ds2Parser::Result r = parser.feed((uint8_t)kSerial.read());
        if (r == Ds2Parser::MORE) continue;
        if (r == Ds2Parser::DONE) onFrame(parser.frame(), parser.length());
        else if (r == Ds2Parser::BAD_ECHO) klineStats.badEcho++;
        else if (r == Ds2Parser::BAD_LEN) klineStats.badLen++;
        else klineStats.badSum++;
        if (r != Ds2Parser::DONE && customInFlight) customReply = "error";
        finish(now);
        return;
    }
    if (now - sentAt > REPLY_TIMEOUT) {
        klineStats.timeouts++;
        if (customInFlight) customReply = "timeout";
        finish(now);
    }
}

String klineStatusString() {
    const KlineStats& s = klineStats;
    return "DS2 " + String(s.hz) + " Hz, tx " + String(s.tx) + " ok " + String(s.ok) + " timeout " + String(s.timeouts) +
           " echo " + String(s.badEcho) + " len " + String(s.badLen) + " sum " + String(s.badSum) + " nack " + String(s.nack);
}

String klineLastFrameHex() {
    return lastLen ? hex(lastFrame, lastLen) : String("-");
}

String klineCustomReplyHex() {
    return customReply;
}
