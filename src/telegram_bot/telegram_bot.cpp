#include <WiFi.h>
#include <WiFiManager.h>
#include <UniversalTelegramBot.h>
#include "config/config.h"
#include "gps_controller/gps_controller.h"
#include "telegram_bot.h"
#include <ArduinoJson.h>

WiFiClient client;  // Use regular WiFiClient for HTTP connections
UniversalTelegramBot bot(BOT_TOKEN, client);
const int botRequestDelay = 1000;
unsigned long lastTimeBotRan;

void initializeTelegramBot() {
    Serial.println("Initializing Telegram Bot...");
    lastTimeBotRan = 0;
}

// Function to handle "get gps" command
void handleGPSCommand(String chat_id) {
    // Get GPS data
    double latitude = getLatitude();
    double longitude = getLongitude();
    double speed = getSpeed();
    double altitude = getAltitude();
    
    // Create a message with the GPS data
    String message = "GPS Data:\n";
    message += "Latitude: " + String(latitude, 6) + "\n";
    message += "Longitude: " + String(longitude, 6) + "\n";
    message += "Speed: " + String(speed) + " km/h\n";
    message += "Altitude: " + String(altitude) + " m\n";

    // Send the message to the Telegram chat
    bool result = bot.sendMessage(chat_id, message, "");
    if (result) {
        Serial.println("Sent GPS data successfully.");
    } else {
        Serial.println("Failed to send GPS data.");
    }
}

// Function to check for Telegram messages
void checkTelegramMessages() {
    if (millis() - lastTimeBotRan > botRequestDelay) {
        Serial.println("Checking for Telegram messages...");
        int numNewMessages = bot.getUpdates(bot.last_message_received + 1);

        if (numNewMessages > 0) {
            Serial.printf("Received %d message(s).\n", numNewMessages);
            for (int i = 0; i < numNewMessages; i++) {
                String chat_id = bot.messages[i].chat_id;
                String text = bot.messages[i].text;

                Serial.println("Message received: " + text);

                if (text == "/getgps") {
                    handleGPSCommand(chat_id);
                } else {
                    bool result = bot.sendMessage(chat_id, "Unknown command! Try /getgps", "");
                    if (!result) {
                        Serial.println("Failed to send message.");
                    }
                }
            }
        } else {
            Serial.println("No new messages.");
        }

        lastTimeBotRan = millis();
    }
}
