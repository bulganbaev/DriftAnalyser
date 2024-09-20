#ifndef HTMLPAGES_H
#define HTMLPAGES_H

// HTML content for the getObd page
const char GET_OBD_PAGE_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML>
<html>
<head>
  <meta http-equiv="refresh" content="2"> <!-- Refresh page every 2 seconds -->
  <title>OBD2 Data</title>
  <style>
    body { font-family: Arial; text-align: center; margin-top: 50px; }
    h1 { color: #333; }
    p { font-size: 24px; }
  </style>
</head>
<body>
  <h1>Vehicle OBD2 Data</h1>
  <p>RPM: %RPM%</p>
  <p>Throttle Position: %THROTTLE%</p>
</body>
</html>
)rawliteral";

#endif // HTMLPAGES_H
