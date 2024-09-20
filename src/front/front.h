#ifndef FRONT_H
#define FRONT_H

#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

// Function to set up the Access Point and web server
void setupAccessPoint();

// Function to handle the web server
void handleWebServer();

// Function to handle requests for OBD2 data
void handleGetObd(AsyncWebServerRequest *request);

// Function to handle requests for log data
void handleGetLogs(AsyncWebServerRequest *request);


#endif // FRONT_H
