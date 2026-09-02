#include "imu.h"
#include <Wire.h>
#include "pins/pins.h"

ImuData imu;

static uint8_t addr = 0;
static unsigned long lastRead = 0;
const unsigned long IMU_INTERVAL = 20;  // 50 Hz
const float LPF = 0.2f;                  // simple low-pass

static bool writeReg(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

static bool probe(uint8_t a) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() != 0) return false;
    Wire.beginTransmission(a);
    Wire.write(0x75);  // WHO_AM_I
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(a, (uint8_t)1) != 1) return false;
    uint8_t who = Wire.read();
    return (who & 0x7E) == 0x68;  // 0x68 for MPU-6050, ignore AD0 bit
}

void imuSetup() {
    pinMode(IMU_SDA_PIN, INPUT_PULLUP);
    pinMode(IMU_SCL_PIN, INPUT_PULLUP);
    delay(5);
    Serial.printf("I2C idle levels: SDA=%d SCL=%d\n", digitalRead(IMU_SDA_PIN), digitalRead(IMU_SCL_PIN));
    Wire.begin(IMU_SDA_PIN, IMU_SCL_PIN, 100000);
    delay(50);
    for (uint8_t a : {0x68, 0x69}) {
        if (probe(a)) { addr = a; break; }
    }
    if (!addr) {
        Serial.print("MPU-6050 not found, I2C scan:");
        int found = 0;
        for (uint8_t a = 1; a < 127; a++) {
            Wire.beginTransmission(a);
            if (Wire.endTransmission() == 0) { Serial.printf(" 0x%02X", a); found++; }
        }
        Serial.println(found ? "" : " nothing");
        return;
    }
    writeReg(0x6B, 0x01);  // wake up, PLL with X gyro ref
    writeReg(0x1A, 0x03);  // DLPF 44 Hz
    writeReg(0x1B, 0x08);  // gyro +-500 deg/s
    writeReg(0x1C, 0x08);  // accel +-4 g
    imu.ok = true;
    Serial.printf("MPU-6050 found at 0x%02X\n", addr);
}

void imuTick() {
    if (!imu.ok) return;
    unsigned long now = millis();
    if (now - lastRead < IMU_INTERVAL) return;
    lastRead = now;

    Wire.beginTransmission(addr);
    Wire.write(0x3B);
    if (Wire.endTransmission(false) != 0) return;
    if (Wire.requestFrom(addr, (uint8_t)14) != 14) return;
    int16_t raw[7];
    for (int i = 0; i < 7; i++) {
        raw[i] = (Wire.read() << 8) | Wire.read();
    }
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
}
