#include "gps_controller.h"
#include <HardwareSerial.h>
#include "pins/pins.h"

// TinyGPS++ object to parse GPS data
TinyGPSPlus gps;

// Function to initialize the GPS module
void initializeGPS() {
    // Begin serial communication with the GPS module using default UART0 (RXD0 and TXD0)
    Serial.begin(9600);  // GPS baud rate (adjust if needed)
    
    // Configure PPS (Pulse Per Second) pin if necessary
    pinMode(GPS_PPS_PIN, INPUT);  // Set GPIO48 as input for PPS signal (if needed for time synchronization)
}

// Function to read data from the GPS module
void readGPSData() {
    while (Serial.available() > 0) {
        gps.encode(Serial.read());
    }
}

// Function to get the current latitude
double getLatitude() {
    if (gps.location.isValid()) {
        return gps.location.lat();
    } else {
        return 0.0;  // Return 0.0 if data is invalid
    }
}

// Function to get the current longitude
double getLongitude() {
    if (gps.location.isValid()) {
        return gps.location.lng();
    } else {
        return 0.0;  // Return 0.0 if data is invalid
    }
}

// Function to get the current speed in km/h
double getSpeed() {
    if (gps.speed.isValid()) {
        return gps.speed.kmph();
    } else {
        return 0.0;  // Return 0.0 if data is invalid
    }
}

// Function to get the current altitude in meters
double getAltitude() {
    if (gps.altitude.isValid()) {
        return gps.altitude.meters();
    } else {
        return 0.0;  // Return 0.0 if data is invalid
    }
}
