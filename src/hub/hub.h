#ifndef HUB_H
#define HUB_H

#include <GyverHub.h>
#include "led_control/led_control.h"
#include "obd2/obd2.h"

extern OBD2 obd2;

void setupHub();
void updateHub();
void build(gh::Builder& b);

#endif // HUB_H
