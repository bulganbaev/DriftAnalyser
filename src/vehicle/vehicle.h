#ifndef VEHICLE_H
#define VEHICLE_H

#include <Arduino.h>
#include "can_bus/can_bus.h"
#include "obd2/obd2.h"

// CAN data source
enum CanMode : int {
    CAN_MODE_OBD2 = 0,     // active OBD2 PID polling
    CAN_MODE_BMW = 1,      // passive decode of BMW MS43 PT-CAN
    CAN_MODE_SNIFFER = 2,  // passive, dump all IDs to Serial
    CAN_MODE_DS2 = 3,      // BMW MS43 over K-line, CAN stays listen-only
};

struct VehicleData {
    uint16_t rpm = 0;
    uint8_t speed = 0;
    uint8_t throttle = 0;
    int8_t temp = 0;
    unsigned long lastUpdate = 0;  // millis of last decoded value
};

extern VehicleData vehicle;
extern int canMode;
extern int canBitrateSel;   // 0 = auto, else CanBitrate + 1 (not persisted)

void vehicleSetBitrate(int sel);
String canBitrateString();

void vehicleSetup(CANBus& can, OBD2& obd);
void vehicleSetMode(int mode);
void vehicleTick();
bool vehicleDataFresh();
String canStatusString();
String sniffTableString();

#endif
