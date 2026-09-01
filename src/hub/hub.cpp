#include "hub.h"
#include <WiFi.h>
#include "settings/settings.h"
#include "net/net.h"
#include "vehicle/vehicle.h"
#include "imu/imu.h"

GyverHub hub;

static int selectedStrip = 0;
static int selectedPreset = 0;
static unsigned long lastUpdate = 0;
const unsigned long updateInterval = 1000;

static const char* SCALE_SOURCES = "RPM;Speed;Throttle;Lateral G;Yaw rate";
static const char* AXES = "+X;-X;+Y;-Y;+Z;-Z";
static const char* ANIMATIONS = "Static Color;Theater Chase;Color Wave;Breathing Light;Rainbow Cycle;Snake;Meteor Rain;Twinkle;Running Lights;Larson Scanner;Fire;Police;Confetti;Color Wipe;Sinelon";

void setupHub() {
    hub.config(F("MyDevices"), F("ZverCUSTOM"), F("💡"));
    hub.onBuild(build);
    hub.begin();
    if (!hub.running()) {
        Serial.println("GyverHub failed to initialize!");
        return;
    }
    Serial.println("GyverHub initialized");
}

void updateHub() {
    hub.tick();
    unsigned long now = millis();
    if (now - lastUpdate < updateInterval) return;
    lastUpdate = now;

    static const char* always[] = {"rpm", "speed", "throttle", "temp", "wifi", "can", "sta", "ap", "latg", "yaw"};
    for (const char* n : always) hub.sendUpdate(n);
    if (canMode == CAN_MODE_SNIFFER) hub.sendUpdate("sniff");
    if (imu.ok && hub.menu == 4) {
        static const char* names[] = {"ax", "ay", "az", "gx", "gy", "gz", "imutemp"};
        for (const char* n : names) hub.sendUpdate(n);
    }
}

static String fmt(float v, int digits = 2) {
    return String(v, digits);
}

static void applyToAllStrips(int from) {
    for (int i = 0; i < NUM_STRIPS; i++) {
        if (i == from) continue;
        StripSettings& d = stripSettings[i];
        const StripSettings& s = stripSettings[from];
        d.mode = s.mode;
        d.animationIndex = s.animationIndex;
        d.color = s.color;
        d.colorOrder = s.colorOrder;
        d.bottom = s.bottom;
        d.center = s.center;
        d.scaleSource = s.scaleSource;
        d.brightness = s.brightness;
    }
}

// ============================ pages ============================

static void buildDashboard(gh::Builder& b) {
    {
        gh::Row r(b);
        b.Switch(&drive.masterOn).label(F("Master")).size(2);
        b.Label_("wifi", netStatusString()).label(F("Wi-Fi")).size(4).fontSize(16);
    }
    int rpm = obd2.getRPM(), speed = obd2.getSpeed(), temp = obd2.getEngineTemp(), thr = obd2.getThrottlePosition();
    float latg = imuLateralG(), yaw = imuYawRate();
    {
        gh::Row r(b);
        b.Gauge_("rpm", &rpm).label(F("RPM")).size(3).range(0, 9000, 1);
        b.Gauge_("speed", &speed).label(F("Speed")).size(3).range(0, 300, 1);
    }
    {
        gh::Row r(b);
        b.Gauge_("temp", &temp).label(F("Temp")).size(3).range(0, 200, 1);
        b.Gauge_("throttle", &thr).label(F("Throttle")).size(3).range(0, 100, 1);
    }
    {
        gh::Row r(b);
        b.Gauge_("latg", &latg).label(F("Lateral G")).size(3).range(-2.0f, 2.0f, 0.01f);
        b.Gauge_("yaw", &yaw).label(F("Yaw deg/s")).size(3).range(-300.0f, 300.0f, 0.1f);
    }
    {
        gh::Row r(b);
        b.Label_("can", canStatusString()).label(F("CAN")).fontSize(16);
    }
    {
        gh::Row r(b);
        if (b.Button().label("Reboot").size(3).click()) {
            settingsSaveNow();
            delay(100);
            ESP.restart();
        }
    }
}

static void buildLeds(gh::Builder& b, bool& forceSave) {
    char buffer[48];
    StripSettings& st = stripSettings[selectedStrip];
    {
        gh::Row r(b);
        b.Select(&selectedStrip).label("Strip").size(2).text("1;2;3;4;5;6");
        snprintf(buffer, sizeof(buffer), "Strip %d enabled", selectedStrip + 1);
        b.Switch(&st.enabled).label(buffer).size(2);
        b.Switch(&st.reverse).label(F("Reverse")).size(2);
    }
    {
        gh::Row r(b);
        b.Select(&st.mode).label(F("Mode")).size(3).text("Animation;Scale;Hybrid");
        if (st.mode > 0) {
            b.Select(&st.scaleSource).label(F("Scale source")).size(3).text(SCALE_SOURCES);
        } else {
            b.Select(&st.animationIndex).label(F("Animation")).size(3).text(ANIMATIONS);
        }
    }
    if (st.mode == 2) {
        gh::Row r(b);
        b.Select(&st.animationIndex).label(F("Animation below min")).size(6).text(ANIMATIONS);
    }
    {
        gh::Row r(b);
        b.Color(&st.color).label(F("Color")).size(2);
        b.Slider(&st.brightness).label(F("Strip brightness")).size(4).range(0, 100, 1);
    }
    {
        gh::Row r(b);
        b.Spinner(&numLedsPerStrip[selectedStrip]).label(F("LED count")).size(3).range(1, MAX_LEDS, 1);
        b.Select(&st.colorOrder).label(F("Color order")).size(3).text("RGB;GRB;BGR;RBG;GBR;BRG");
    }
    if (st.mode > 0) {
        gh::Row r(b);
        b.Switch(&st.bottom).label(F("Grow from middle")).size(3);
        if (st.bottom) {
            b.Spinner(&st.center).label(F("Middle LED")).size(3).range(0, numLedsPerStrip[selectedStrip], 1);
        }
    }
    {
        gh::Row r(b);
        if (b.Button().label("Apply to all strips").size(6).click()) {
            applyToAllStrips(selectedStrip);
            forceSave = true;
        }
    }
    b.Title(F("Global"));
    {
        gh::Row r(b);
        b.Slider(&can_setting.speed).label(F("Animation speed")).size(3).range(0, 100, 1);
        b.Slider(&can_setting.brightess).label(F("Global brightness")).size(3).range(0, 100, 1);
    }
    {
        gh::Row r(b);
        b.Spinner(&can_setting.minRPM).label(F("Scale min RPM")).size(3).range(0, 12000, 100);
        b.Spinner(&can_setting.maxRPM).label(F("Scale max RPM")).size(3).range(0, 12000, 100);
    }
    {
        gh::Row r(b);
        b.Spinner(&drive.shiftRPM).label(F("Shift light RPM (0 = max)")).size(3).range(0, 12000, 100);
        b.Color(&drive.shiftColor).label(F("Shift color")).size(3);
    }
    {
        gh::Row r(b);
        b.Spinner(&drive.maxLateralG).label(F("Full scale G")).size(3).range(0.2f, 3.0f, 0.1f);
        b.Spinner(&drive.maxYawRate).label(F("Full scale yaw")).size(3).range(10.0f, 300.0f, 10.0f);
    }
    {
        gh::Row r(b);
        b.Select(&drive.engineOff).label(F("Engine off / no data")).size(3).text("Keep running;Dim;Off");
        if (drive.engineOff == 1) b.Slider(&drive.engineOffDim).label(F("Dim to %")).size(3).range(0, 100, 1);
    }
    {
        gh::Row r(b);
        b.Spinner(&drive.powerLimitMa).label(F("Power limit mA (0 = off)")).size(6).range(0, 30000, 500);
    }
    b.Title(F("Presets"));
    {
        gh::Row r(b);
        String names;
        for (int i = 0; i < NUM_PRESETS; i++) {
            if (i) names += ';';
            names += String(i + 1) + ": " + settingsPresetName(i);
        }
        b.Select(&selectedPreset).label(F("Preset")).size(2).text(names);
        if (b.Button().label("Load").size(2).click()) {
            if (settingsPresetLoad(selectedPreset)) hub.sendRefresh();
        }
        if (b.Button().label("Save").size(2).click()) {
            settingsPresetSave(selectedPreset);
            hub.sendRefresh();
        }
    }
}

static void buildCan(gh::Builder& b) {
    {
        gh::Row r(b);
        if (b.Select(&canMode).label("CAN Source").text("OBD2;BMW MS43;Sniffer").click()) {
            vehicleSetMode(canMode);
        }
    }
    {
        gh::Row r(b);
        b.Label_("can", canStatusString()).label(F("CAN")).fontSize(16);
    }
    {
        gh::Row r(b);
        b.Label_("rpm", String(obd2.getRPM())).label(F("RPM")).size(2);
        b.Label_("speed", String(obd2.getSpeed())).label(F("Speed")).size(2);
        b.Label_("temp", String(obd2.getEngineTemp())).label(F("Temp")).size(2);
        b.Label_("throttle", String(obd2.getThrottlePosition())).label(F("Throttle")).size(2);
    }
    if (canMode == CAN_MODE_SNIFFER) {
        gh::Row r(b);
        b.Text_("sniff", sniffTableString()).label(F("CAN frames")).rows(20).size(6);
    }
}

static void buildWifi(gh::Builder& b) {
    {
        gh::Row r(b);
        b.Input(&wifiSsid).label("Wi-Fi SSID").size(3).maxLen(32);
        b.Pass(&wifiPass).label("Wi-Fi Password").size(3).maxLen(64);
    }
    {
        gh::Row r(b);
        if (b.Button().label("Reconnect").size(6).click()) netReconnect();
    }
    {
        gh::Row r(b);
        b.Label_("wifi", netStatusString()).label(F("Status")).fontSize(16);
    }
    {
        gh::Row r(b);
        b.Label_("sta", netStaString()).label(F("STA IP")).fontSize(16);
    }
    {
        gh::Row r(b);
        b.Label_("ap", netApString()).label(F("Access Point")).fontSize(16);
    }
    {
        gh::Row r(b);
        b.Label(WiFi.macAddress()).label(F("MAC")).fontSize(16);
    }
}

static void buildImu(gh::Builder& b) {
    if (!imu.ok) {
        gh::Row r(b);
        b.Label(F("MPU-6050 not responding")).label(F("IMU")).size(6);
        return;
    }
    float latg = imuLateralG(), yaw = imuYawRate();
    {
        gh::Row r(b);
        b.Gauge_("latg", &latg).label(F("Lateral G")).size(3).range(-2.0f, 2.0f, 0.01f);
        b.Gauge_("yaw", &yaw).label(F("Yaw deg/s")).size(3).range(-300.0f, 300.0f, 0.1f);
    }
    {
        gh::Row r(b);
        b.Select(&drive.lateralAxis).label(F("Lateral axis")).size(3).text(AXES);
        b.Select(&drive.yawAxis).label(F("Yaw axis")).size(3).text(AXES);
    }
    {
        gh::Row r(b);
        if (b.Button().label("Calibrate (car level, engine off)").size(6).click()) {
            imuCalibrate();
            settingsSave();
        }
    }
    {
        gh::Row r(b);
        b.Label_("ax", fmt(imu.ax)).label(F("Accel X, g")).size(2);
        b.Label_("ay", fmt(imu.ay)).label(F("Accel Y, g")).size(2);
        b.Label_("az", fmt(imu.az)).label(F("Accel Z, g")).size(2);
    }
    {
        gh::Row r(b);
        b.Label_("gx", fmt(imu.gx, 1)).label(F("Gyro X, deg/s")).size(2);
        b.Label_("gy", fmt(imu.gy, 1)).label(F("Gyro Y, deg/s")).size(2);
        b.Label_("gz", fmt(imu.gz, 1)).label(F("Gyro Z, deg/s")).size(2);
    }
    {
        gh::Row r(b);
        b.Label_("imutemp", fmt(imu.temp, 1)).label(F("IMU temp, C")).size(3);
    }
}

void build(gh::Builder& b) {
    bool forceSave = false;

    b.Menu(F("Dashboard;LEDs;CAN;Wi-Fi;IMU"));

    switch (b.menu()) {
        case 0: buildDashboard(b); break;
        case 1: buildLeds(b, forceSave); break;
        case 2: buildCan(b); break;
        case 3: buildWifi(b); break;
        case 4: buildImu(b); break;
    }

    if (b.changed() || forceSave) {
        for (int i = 0; i < NUM_STRIPS; i++) init(i);
        settingsSave();
        hub.sendRefresh();
    }
}
