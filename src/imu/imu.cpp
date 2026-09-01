#include "imu.h"
#include <Wire.h>
#include "pins/pins.h"

ImuData imu;

static uint8_t addr = 0;
static unsigned long lastRead = 0;
static unsigned long lastInitTry = 0;
static int readFails = 0;
static int samplesToPrint = 0;
const unsigned long IMU_INTERVAL = 20;     // 50 Hz
const unsigned long IMU_RETRY = 5000;      // re-probe when not found
const float LPF = 0.2f;                    // simple low-pass

static bool writeReg(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

static bool readRegs(uint8_t reg, uint8_t* buf, uint8_t len) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(addr, len) != len) return false;
    for (uint8_t i = 0; i < len; i++) buf[i] = Wire.read();
    return true;
}

static bool ack(uint8_t a) {
    Wire.beginTransmission(a);
    return Wire.endTransmission() == 0;
}

static bool tryInit() {
    addr = 0;
    for (uint8_t a : {0x68, 0x69}) {
        if (ack(a)) { addr = a; break; }
    }
    if (!addr) return false;

    uint8_t who = 0;
    readRegs(0x75, &who, 1);
    Serial.printf("MPU-6050 at 0x%02X, WHO_AM_I=0x%02X\n", addr, who);

    bool ok = writeReg(0x6B, 0x80);  // reset
    delay(100);
    ok &= writeReg(0x6B, 0x01);      // wake, PLL X gyro
    ok &= writeReg(0x1A, 0x03);      // DLPF 44 Hz
    ok &= writeReg(0x1B, 0x08);      // gyro +-500 deg/s
    ok &= writeReg(0x1C, 0x08);      // accel +-4 g
    if (!ok) {
        Serial.println("MPU-6050 config write failed");
        return false;
    }
    readFails = 0;
    samplesToPrint = 3;
    return true;
}

void imuSetup() {
    pinMode(IMU_SDA_PIN, INPUT_PULLUP);
    pinMode(IMU_SCL_PIN, INPUT_PULLUP);
    delay(5);
    Serial.printf("I2C idle levels: SDA=%d SCL=%d\n", digitalRead(IMU_SDA_PIN), digitalRead(IMU_SCL_PIN));
    Wire.begin(IMU_SDA_PIN, IMU_SCL_PIN, 100000);
    Wire.setTimeOut(5);
    delay(50);
    imu.ok = tryInit();
    lastInitTry = millis();
    if (!imu.ok) Serial.println("MPU-6050 not found, will retry");
}

void imuTick() {
    unsigned long now = millis();
    if (!imu.ok) {
        if (now - lastInitTry < IMU_RETRY) return;
        lastInitTry = now;
        imu.ok = tryInit();
        return;
    }
    if (now - lastRead < IMU_INTERVAL) return;
    lastRead = now;

    uint8_t buf[14];
    if (!readRegs(0x3B, buf, 14)) {
        if (++readFails >= 10) {
            Serial.println("MPU-6050 lost");
            imu.ok = false;
            lastInitTry = now;
        }
        return;
    }
    readFails = 0;
    int16_t raw[7];
    for (int i = 0; i < 7; i++) raw[i] = (buf[2 * i] << 8) | buf[2 * i + 1];

    // +-4 g -> 8192 LSB/g, +-500 deg/s -> 65.5 LSB/(deg/s)
    float ax = raw[0] / 8192.0f, ay = raw[1] / 8192.0f, az = raw[2] / 8192.0f;
    float t = raw[3] / 340.0f + 36.53f;
    float gx = raw[4] / 65.5f, gy = raw[5] / 65.5f, gz = raw[6] / 65.5f;

    imu.ax += (ax - imu.ax) * LPF;
    imu.ay += (ay - imu.ay) * LPF;
    imu.az += (az - imu.az) * LPF;
    imu.gx += (gx - imu.gx) * LPF;
    imu.gy += (gy - imu.gy) * LPF;
    imu.gz += (gz - imu.gz) * LPF;
    imu.temp = t;
    imu.lastUpdate = now;

    if (samplesToPrint > 0 && (now / IMU_INTERVAL) % 25 == 0) {
        samplesToPrint--;
        Serial.printf("IMU a=%.2f %.2f %.2f g  g=%.1f %.1f %.1f dps  t=%.1f\n", imu.ax, imu.ay, imu.az, imu.gx, imu.gy, imu.gz, imu.temp);
    }
}
