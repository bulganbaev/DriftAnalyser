
#ifndef GPS_CONTROLLER_H
#define GPS_CONTROLLER_H

#include <TinyGPS++.h>

// GPS-related functions and data
void initializeGPS();
void readGPSData();
double getLatitude();
double getLongitude();
double getSpeed();
double getAltitude();

// Declare the GPS object (TinyGPS++ instance)
extern TinyGPSPlus gps;

#endif
