#ifndef IMU_H
#define IMU_H

#include <Arduino.h>

// LSM6DS3TR-C on board I2C
struct ImuData {
    bool ok = false;
    float ax = 0, ay = 0, az = 0;  // g
    float gx = 0, gy = 0, gz = 0;  // deg/s
    float temp = 0;                // C
    unsigned long lastUpdate = 0;
};

extern ImuData imu;

void imuSetup();
void imuTick();
void imuCalibrate();      // current rest reading becomes zero
float imuLateralG();      // along drive.lateralAxis, offset removed
float imuYawRate();       // deg/s along drive.yawAxis, offset removed

#endif
