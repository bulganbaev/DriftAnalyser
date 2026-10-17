#ifndef KLINE_H
#define KLINE_H

#include <Arduino.h>
#include <ds2.h>

// BMW DS2 over the TJA1027 K-line, polls the MS43 status block
struct KlineStats {
    uint32_t tx = 0, ok = 0, timeouts = 0, badEcho = 0, badLen = 0, badSum = 0, nack = 0;
    uint32_t hz = 0;   // good replies in the last second
};

extern KlineStats klineStats;
extern Ms43Status ms43;

void klineBegin();
void klineTick();                                   // poll loop, never blocks
bool klineSendCustom(const uint8_t* raw, size_t n);  // addr, len, data; xor is appended
String klineStatusString();
String klineLastFrameHex();
String klineCustomReplyHex();

#endif
