#ifndef HUB_H
#define HUB_H

#include <GyverHub.h>
#include "led_control/led_control.h"
#include "obd2/obd2.h"

// Declare external variables for the settings
extern StripSettings stripSettings[NUM_STRIPS];
extern CanSettings can_setting;
extern OBD2 obd2;

// Function prototypes
void setupHub();
void updateHub();
void build(gh::Builder& b);

#endif // HUB_H
