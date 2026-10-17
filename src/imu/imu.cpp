#include "imu.h"
#include <Wire.h>
#include "pins/pins.h"
#include "settings/settings.h"
#include "system/system.h"

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
    for (uint8_t a : {0x6A, 0x6B}) {
        if (ack(a)) { addr = a; break; }
    }
    if (!addr) return false;

    uint8_t who = 0;
    readRegs(0x0F, &who, 1);
    sysLog("LSM6DS3TR-C at 0x" + String(addr, HEX) + " WHO_AM_I=0x" + String(who, HEX));
    if (who != 0x6A) return false;

    bool ok = writeReg(0x12, 0x01);  // CTRL3_C: software reset
    delay(10);
    ok &= writeReg(0x12, 0x44);      // CTRL3_C: BDU, auto-increment
    ok &= writeReg(0x10, 0x48);      // CTRL1_XL: 104 Hz, +-4 g
    ok &= writeReg(0x11, 0x44);      // CTRL2_G: 104 Hz, +-500 deg/s
    if (!ok) {
        Serial.println("LSM6DS3TR-C config write failed");
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
    if (!imu.ok) Serial.println("LSM6DS3TR-C not found, will retry");
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
    if (!readRegs(0x20, buf, 14)) {
        if (++readFails >= 10) {
            sysLog(F("LSM6DS3TR-C lost"));
            imu.ok = false;
            lastInitTry = now;
        }
        return;
    }
    readFails = 0;
    // OUT_TEMP, gyro XYZ, accel XYZ; little-endian
    int16_t raw[7];
    for (int i = 0; i < 7; i++) raw[i] = (int16_t)(buf[2 * i] | (buf[2 * i + 1] << 8));

    // +-4 g -> 0.122 mg/LSB, +-500 deg/s -> 17.5 mdps/LSB
    float t = raw[0] / 256.0f + 25.0f;
    float gx = raw[1] * 0.0175f, gy = raw[2] * 0.0175f, gz = raw[3] * 0.0175f;
    float ax = raw[4] * 0.000122f, ay = raw[5] * 0.000122f, az = raw[6] * 0.000122f;

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

static float axisValue(const float* v, const float* off, int axis) {
    int i = constrain(axis, 0, 5) / 2;
    float x = v[i] - off[i];
    return (axis & 1) ? -x : x;
}

void imuCalibrate() {
    if (!imu.ok) return;
    drive.accOff[0] = imu.ax;
    drive.accOff[1] = imu.ay;
    drive.accOff[2] = imu.az;
    drive.gyrOff[0] = imu.gx;
    drive.gyrOff[1] = imu.gy;
    drive.gyrOff[2] = imu.gz;
    Serial.println("IMU calibrated");
}

float imuLateralG() {
    if (!imu.ok) return 0;
    float a[3] = {imu.ax, imu.ay, imu.az};
    return axisValue(a, drive.accOff, drive.lateralAxis);
}

float imuYawRate() {
    if (!imu.ok) return 0;
    float g[3] = {imu.gx, imu.gy, imu.gz};
    return axisValue(g, drive.gyrOff, drive.yawAxis);
}
