# DriftAnalyser PCB v2

Вторая ревизия платы. Дизайн сгенерирован из `gen/model.py` + `gen/placement.py`
скриптом (`gen/build.sh`), сам KiCad-проект (`driftanalyser-v2.kicad_pro` и
остальные `.kicad_*` в этой папке) — результат генерации, руками там лучше не лазить,
следующий пересбор всё затрёт. Fab-файлы под заказ в `fab/`, там же
`fab/README-fab.md` с опциями заказа у JLC и что проверить в руки перед подачей питания
первый раз — читать вместе с этим файлом, не дублирую здесь.

## Что это и чем отличается от v1

Старая плата (`PCB/`, EasyEDA-схема) сейчас стоит в машине, её README живёт в корне
репозитория. У неё врождённые проблемы: 7805 не тянет ленты, MPU-6050 с недорисованной
обвязкой, перепутанная шелкография LED3/LED5, клеммники 3.81, неиспользуемые реле/GPS.
v2 — не патч, а плата с нуля под реальное применение (12В ленты WS2815 на дрифт-машине
с CAN/K-line от BMW MS43):

- **Только 12В ленты.** 5В части на плате больше нет вообще — ни линейника 7805, ни
  разъёма под 5В ленту. Кто хочет 5В ленту — питает её внешним DC-DC, на разъём заводит
  только DATA/GND (как и раньше на v1, только теперь это единственный вариант).
- Силовой ключ лент — Infineon **BTS7002-1EPP** (PROFET+2, встроенная защита от КЗ,
  перегрева, обратки, аналоговый выход тока IS) вместо голого реле/транзистора.
- CAN-трансивер **TJA1051T/3** (3.3В логика, вместо TJA1050 + сдвигателей уровня на v1).
- Добавлен K-line трансивер **TJA1027T/20** (LIN-совместимый) — v1 K-line вообще не умела,
  диагностика MS43 по K-line была недоступна.
- IMU заменён на **LSM6DS3TR-C** (MPU-6050 снят с производства, на рынке в основном контрафакт).
- Убрано: реле×2, посадочное место GPS NEO-6M, TXB0108, 7805, AMS1117, клеммники 3.81мм —
  ничего из этого не использовалось в прошивке или работало плохо.
- Разъёмы питания и лент поменялись: XT60PW вместо клеммника, JST VH 3-пин на ленту
  (12V/DATA/GND) вместо клеммника с перемычками выбора напряжения.
- Плата **4-слойная**, 110×75мм, JLC04161H-7628 1.6мм (спека изначально предполагала
  2 слоя — при трассировке 20А силовой шины на двух слоях не хватало места и трассы
  ужимались в опасно узкие коридоры, перешли на 4 слоя: In1 сплошная земля, In2 — VBAT
  и 12V_LED полигоны, см. "Питание и пределы" ниже).
- Прошивка **пока не тронута** и таргетится на v1 — карта пинов, драйвер IMU и всё
  остальное под v2 не написаны, см. "Что осталось руками" ниже.

## Как пересобрать

```
bash PCB/v2/gen/build.sh
```

Пересобирает всё по порядку: схему из `gen/model.py`, плату и расстановку из
`gen/placement.py`, трассировку, DRC/ERC, экспорт в `fab/`, прогоняет тесты
(`gen/tests`).

Требования:
- KiCad 10, установлен в `/Applications` (`build.sh` дёргает питон прямо из
  `KiCad.app/Contents/Frameworks/Python.framework/...`, кастомный путь в системе не подхватится).
- Java для Freerouting: `/opt/homebrew/opt/openjdk/bin/java` (переопределяется переменной
  `JAVA`). Freerouting 2.4.1 хочет Java ≥25, системный `/usr/bin/java` на macOS обычно старее.
- Freerouting jar в `~/.local/freerouting/freerouting.jar`.

**Трассировка не гоняется на каждой пересборке** — она реплеится из закоммиченного
`fab/route.ses`. `DA2_REROUTE=1` просит у Freerouting новый прогон: он недетерминирован
(порядок объектов, не фиксированный seed), результат может отличаться от того что в
репозитории и может оставить открытые связи — если рероутишь, проверяй DRC-отчёт заново.
Треки и переходные, которые билдер рисует руками **до** импорта SES, реплей затирает —
переживают только шаги **после** импорта (например `vbat_stitch`, который доливает
переходные в VBAT-полигон уже после трассировки).

Тяжёлый экспорт (STEP, 3D-рендеры) — под `DA2_HEAVY=1` (в `build.sh` включено по
умолчанию), в git не лежит. `fab/gerbers.zip` — единственный трекнутый файл, который
меняется при каждой пересборке даже когда плата не менялась: KiCad пишет свежий
`CreationDate` внутрь каждого гербер-файла, это честная метка когда файлы сделаны,
специально не чистится.

Изменения вносить в `gen/model.py` (детали, пины, номиналы) и `gen/placement.py`
(расположение) — не в сгенерённых `.kicad_sch`/`.kicad_pcb` напрямую, их перезатрёт
следующий `build.sh`.

## Разъёмы и распиновки

| Разъём | Тип | Пины |
|---|---|---|
| J1 PWR | XT60PW-M | 1 GND, **2 +12V** (левая дырка если смотреть на разъём, «+» на шелкографии — см. предупреждение ниже) |
| J11..J16 LED1..LED6 | JST VH B3P-VH 3-пин | 1 12V, 2 DATA, 3 GND |
| J6 OBD | JST XH 4-пин | 1 CANH, 2 CANL, 3 K, 4 GND |
| J2 USB | USB-C 16-пин | нативный USB на ESP32-S3 (D+/D- GPIO20/19) |
| J3 UART0 | 1×4 header 2.54мм | 1 3V3, 2 GND, 3 TX (GPIO43), 4 RX (GPIO44) — аварийная прошивка через UART |
| J4 EXT | 1×6 header 2.54мм | 1 3V3, 2 GND, 3 TX2 (GPIO35), 4 RX2 (GPIO36), 5 SDA (GPIO8), 6 SCL (GPIO9) — под будущую телеметрию |
| J5 microSD | push-push, SDMMC 4-бит | не задействован в прошивке |

J3/J4 стоят справа от ESP32 (x≈29.5/35мм, y 20..36мм) — не в углу платы, как можно
подумать по старой привычке от v1.

**Полярность XT60PW проверена по геометрии в библиотеке KiCad и конвенции AMASS/XT60
(скошенный торец корпуса — минус, прямой — плюс), но не по живому разъёму. Перед первым
включением прозвонить тестером конкретную пару XT60, которая пойдёт в машину** — не
поленись, а то спалишь плату на первой секунде.

## Джамперы

- **JP1 CAN TERM** — 120 Ом между CANH/CANL. Снять, если плата подключается к готовой
  шине машины (там свои терминаторы, MS43 в частности). Ставить, только если плата —
  физический конец CAN-шины.
- **JP2 K PULLUP** — 510 Ом 0.5Вт от K-line к VBAT (тестерная подтяжка по ISO 9141).
  Ставить, если ECU сам не подтягивает линию K. У большинства ECU подтяжка своя —
  джампер обычно снят, пробовать без него сначала.

## Подключение WS2815

- У WS2815 4 провода на пиксель (5В/12В, GND, DATA, BI — backup-in, резервная линия
  для детекта обрыва данных), а на плате разъём **3-пиновый** (12V/DATA/GND). BI на
  разъём не выведен — подключается прямо **на самой ленте**, у первого пикселя,
  замыкается на GND. Без этого лента может не стартовать вообще (у WS2815 есть
  автоматический детект обрыва по BI).
- Подключать разъём к **началу** ленты (input end), не к середине и не к хвосту —
  иначе адресация светодиодов в прошивке не совпадёт с физикой.
- Сечение проводов от разъёма до ленты: питание 1.0–1.5 мм², данные 0.5 мм² хватает
  с запасом.
- До ~2м ленты 144/м на один разъём — дальше просадка по длине и ток на контакте JST
  VH (рейтинг 10А/пин) уже неприятный.

## Питание и пределы

- Вход 9–16В штатно, XT60PW. TVS D1 (SMDJ18A) на VBAT держит броски. 3S LiPo — ок,
  4S/6S — нет, слишком высокое напряжение для линейки лент/буков.
- Предохранитель — **один, 30А, в жгуте у аккумулятора**, не на плате. Каналы лент
  защищает сам BTS7002-1EPP (тепловое отключение + авторестарт встроены в чип), IS
  выведен в прошивку через GPIO2 (ADC), но само чтение и программный латч по IS ещё
  не написаны — см. "Что осталось руками".
- **Continuous rating по силовой шине VBAT/12V — 20А**, это потолок, который держит
  посадка ключа BTS7002 (тепловое сопротивление корпуса/пятака), и это же — самое
  узкое сечение всей платы: VBAT-коридор под ESP/буком, 20.0А в самом худшем срезе.
  Запаса там почти нет, это край допуска, а не комфортная цифра.
- **Эта цифра держится только если при заказе у JLC явно выбрать 1 oz inner copper**
  (не дефолт для 4-слойной платы — дефолт 0.5 oz). На дефолтной 0.5 oz внутренняя медь
  VBAT-коридор садится примерно вдвое, до ~12А — с ключом на 20А номинальных это уже
  не запас, а прямой путь погреть плату. Подробности и цифры по остальным силовым
  дорожкам — в `fab/README-fab.md`.

## Карта GPIO

Пины по факту разведённой платы (сверено с `gen/model.py`, U1 = ESP32-S3-WROOM-1-N16R2):

| GPIO | Назначение | Заметка |
|---|---|---|
| 0 | BOOT | strapping |
| 1 | VBAT_SENSE | ADC1, делитель 47k/10k |
| 2 | LED_ISENSE | ADC1, выход IS ключа BTS7002 |
| 4 | LED1 DATA | → 74HCT245 A1 → JST VH pin2 |
| 5 | LED2 DATA | → 74HCT245 A2 |
| 6 | LED3 DATA | → 74HCT245 A3 |
| 7 | LED4 DATA | → 74HCT245 A4 |
| 15 | LED5 DATA | → 74HCT245 A5 |
| 16 | LED6 DATA | → 74HCT245 A6 |
| 8 | I2C SDA | IMU + разъём EXT (pin5) |
| 9 | I2C SCL | IMU + разъём EXT (pin6) |
| 10 | LED_PWR_EN | → BTS7002 IN, подтянут вниз 10k (ленты выключены пока прошивка не включит) |
| 11 | STATUS_LED | |
| 12 | K_RX | UART1, TJA1027 RXD |
| 13 | K_TX | UART1, TJA1027 TXD |
| 14 | CAN_STB | → TJA1051 S |
| 17 | IMU_INT1 | |
| 18 | CAN_TX | → TJA1051 TXD |
| 19 / 20 | USB D- / D+ | нативный USB |
| 21 | CAN_RX | ← TJA1051 RXD |
| 35 / 36 | UART2 TX / RX | разъём EXT (pin3/4) |
| 38 / 39 / 40 / 41 / 42 | SD CMD / CLK / D0 / D1 / D2 | SDMMC 4-бит, подтяжки 10k |
| 47 | SD D3 | подтяжка 10k |
| 48 | SD_CD | card detect |
| 43 / 44 | UART0 TX / RX | разъём J3 |
| 3, 45, 46 | не используются | strapping, оставлены свободными |

## Корпус

`enclosure/enclosure.py`, CadQuery в `enclosure/.venv` (Python 3.11):

```
enclosure/.venv/bin/python enclosure/enclosure.py
```

→ `enclosure/out/{base,lid}.stl`, `enclosure/out/enclosure.step`. Флаг `--parts`
дополнительно рисует тела компонентов по отдельности (удобно проверять клиренсы).

Параметры собраны в начале файла: стенка 2.4мм, дно 2мм, стойки под M3 (4.0мм
отверстие под термовставку либо 2.5мм под саморез в пластик), крышка на защёлках
(snap-fit), уши под винты 4мм, вентиляционные прорези над горячей зоной (BTS7002,
буковский/LDO участок).

## Что осталось руками / известные ограничения

- **Прошивка не переписана под v2** и всё ещё таргетится на старую карту пинов v1.
  Нужно (в прошивке, не здесь): новая `pins.h` под таблицу GPIO выше, драйвер
  LSM6DS3TR-C взамен MPU-6050, управление LED_PWR_EN с программным латчем по IS
  (сейчас включение ленты аппаратно защищено ключом, но софт ток не читает и сам
  не отключается), чтение VBAT_SENSE по ADC, DS2/K-line поверх UART1 (TJA1027).
- GNSS/RTK телеметрия — отдельный проект и отдельное железо, на этой плате только
  разъём EXT (см. таблицу разъёмов) для связи с ней.
- XT60 полярность выверена по библиотеке, не по живому разъёму — прозвонить перед
  первым включением (см. предупреждение выше).
- VBAT-коридор держит заявленные 20А только при явном выборе 1 oz inner copper при
  заказе у JLC — дефолт этот минимум срезает почти вдвое (см. "Питание и пределы").
- Посадочные места ESP32-модуля используют термопереходные 0.2мм — у JLC это
  доплата (min hole 0.2мм), у остального на плате 0.4мм и крупнее.
- IMU LSM6DS3TR-C в корпусе LGA-14, шаг 0.5мм, под ним clearance-правило 0.15мм —
  самое мелкое место на плате. Руками паяется тяжело, ENIG в качестве финишного
  покрытия облегчает (см. `fab/README-fab.md`).
- Всё, что Freerouting не дотрассировал автоматически — ничего: закоммиченный
  `fab/route.ses` даёт полностью разведённую плату (0 DRC violations, 0
  unconnected items, 0 schematic parity). Но пересборка с `DA2_REROUTE=1` может
  оставить открытые связи заново — тогда список будет в выводе `gen.route`,
  проверять DRC-отчёт перед тем как доверять новому прогону.

## BOM sources

All LCSC codes below were looked up live in this session (2026-09-06) via the
JLCPCB parts mirror `jlcsearch.tscircuit.com` (JSON API, `/list?...` query
params per category: `resistance`/`capacitance` in base units + `package`
for passives) and/or `lcsc.com/product-detail/<code>.html` product pages
(via WebFetch) and `WebSearch "<MPN>" site:lcsc.com`. Stock is a snapshot at
lookup time and will drift.

| Ref(s) | Value | MPN | LCSC | JLC type | Stock seen | Date |
|---|---|---|---|---|---|---|
| J1 | XT60PW-M | XT60PW-M | C98732 | Extended | 27,130 | 2026-09-06 |
| D1 | SMDJ18A | 5.0SMDJ18A (DOWO) | C284071 | Extended | 2,925 | 2026-09-06 |
| C1, C2 | 100uF 35V | GVZ1H107M0810CNVC (HRK) | C2983550 | Extended | 66,426 | 2026-09-06 |
| C3, C4, C5, C6, C9 | 10uF 50V | CS3225X7R106K500NRL (SAMWHA) | C2918502 | Extended | 114,648 | 2026-09-06 |
| U2 | BTS7002-1EPP | BTS70021EPPXUMA1 (Infineon) | C2680407 | Extended | 273 | 2026-09-06 |
| U2 fallback | BTS7004-1EPP | BTS7004-1EPP (Infineon) | C534825 | Extended | 3,100 (4.4mOhm, 15A, same TSDSO-14 pkg/pinout, drop-in if 7002 out at order time) | 2026-09-06 |
| R1, R2, R4, R8, R11, R12, R16-R21, R41 | 10k | 0603WAF1002T5E (UNI-ROYAL) | C25804 | Basic | 37,165,617 | 2026-09-06 |
| R5 | 470 | 0603WAF4700T5E (UNI-ROYAL) | C23179 | Basic | 2,964,915 | 2026-09-06 |
| R6, R10, R13 | 1k | 0603WAF1001T5E (UNI-ROYAL) | C21190 | Basic | 15,873,089 | 2026-09-06 |
| C7, C8, C10, C17, C20, C21, C22, C23, C24, C25 | 100nF | CC0603KRX7R9BB104 (YAGEO) | C14663 | Basic | 81,299,425 | 2026-09-06 |
| D2 | BAT54W | BAT54W (JSCJ) | C77328 | Extended | 4,671-7,360 | 2026-09-06 |
| R7 | 47k | 0603WAF4702T5E (UNI-ROYAL) | C25819 | Basic | 5,115,474 | 2026-09-06 |
| U3 | AP63200WU-7 | AP63200WU-7 (Diodes Inc) | C2071868 | Extended | lcsc.com retail: 0/Out of Stock; JLC assembly mirror: 2,599 - kept, two pools differ | 2026-09-06 |
| U3 fallback | TPS54302DDCR | TPS54302DDCR (TI) | C311983 | Extended | 84,590 (adjustable 4.5-28V; needs FB divider 80.6k/10k for 5.4V @ 0.596V ref + EN divider; requires redrawing U3, not done) | 2026-09-06 |
| L1 | 6.8uH | YNR6045-6R8M (YJYCOIN) | C341066 | Extended | 8,265 | 2026-09-06 |
| C11, C12, C13, C16 | 22uF 10V | CL21A226MAQNNNE (Samsung Electro-Mechanics) | C45783 | Basic | 5,389,915 | 2026-09-06 |
| R3 | 57.6k | FRC0603F5762TS (FOJAN) | C2933240 | Extended | 25,989 | 2026-09-06 |
| R9 | 100k | 0603WAF1003T5E (UNI-ROYAL) | C25803 | Basic | 14,797,688 | 2026-09-06 |
| D3, D4 | SS34 | SS34 (MDD) | C8678 | Basic | 3,282,802 | 2026-09-06 |
| U4 | AP7361C-33E | AP7361C-33E-13 (Diodes Inc) | C500795 | Extended | 5,442 | 2026-09-06 |
| C14, C15, C19 | 10uF | CL21A106KAYNNNE (Samsung Electro-Mechanics) | C15850 | Basic | 12,668,317 | 2026-09-06 |
| D5 | BLUE | XL-1608UBC-04 (XINGLIGHT) | C965807 | Extended | 1,829,633 | 2026-09-06 |
| U1 | ESP32-S3-WROOM-1-N16R2 | ESP32-S3-WROOM-1-N16R2 (Espressif) | C2913205 | Extended | 8,701 | 2026-09-06 |
| C18 | 1uF | CL10A105KB8NNNC (Samsung Electro-Mechanics) | C15849 | Basic | 11,240,988 | 2026-09-06 |
| SW1, SW2 | EN/BOOT tactile | PTS645SM43SMTR92LFS (C&K) | C221880 | Extended | 5,900 | 2026-09-06 |
| D6 | GREEN | PSC-1608U49GC-G4 (HONGLITRONIC) | C22371299 | Extended | 24,430 | 2026-09-06 |
| J2 | USB-C 16P | TYPE-C 16PIN 2MD(073) (SHOU HAN) | C2765186 | Extended | (known-good, reused from old BOM) | 2026-09-06 |
| R14, R15 | 5.1k | 0603WAF5101T5E (UNI-ROYAL) | C23186 | Basic | 7,571,904 | 2026-09-06 |
| U6 | USBLC6-2SC6 | USBLC6-2SC6 (ST) | C7519 | Extended | 44,150 | 2026-09-06 |
| J3 | 1x4 header | PZ254V-11-04P (XFCN) | C2691448 | Extended | 1,087,760 | 2026-09-06 |
| J4 | 1x6 header | PZ254V-11-06P (XFCN) | C492405 | Extended | 79,320 | 2026-09-06 |
| J5 | microSD | DM3BT-DSF-PEJS (Hirose) | C597972 | Extended | 1,271 | 2026-09-06 |
| U5 | LSM6DS3TR-C | LSM6DS3TR-C (STMicroelectronics) | C967633 | Extended | 24,304 | 2026-09-06 |
| R22, R23 | 4.7k | 0603WAF4701T5E (UNI-ROYAL) | C23162 | Basic | 9,126,951 | 2026-09-06 |
| U7 | 74HCT245PW | 74HCT245PW,118 (Nexperia) | C5980 | Extended | 6,106 | 2026-09-06 |
| R31-R36 | 220 | 0603WAF2200T5E (UNI-ROYAL) | C22962 | Basic | 3,413,507 | 2026-09-06 |
| D11-D16 | PESD5V0S1BA | PESD5V0S1BA,115 (Nexperia) | C19224 | Extended | 50,425 | 2026-09-06 |
| J11-J16 | LED1-LED6 (JST VH 3-pin) | B3P-VH(LF)(SN) (JST) | C160316 | Extended | 27,734 | 2026-09-06 |
| J6 | OBD (JST XH 4-pin) | B4B-XH-A(LF)(SN) (JST) | C144395 | Extended | 611 | 2026-09-06 |
| U8 | TJA1051T/3 | TJA1051T/3,118 (NXP) | C58988 | Extended | 15,240 | 2026-09-06 |
| R40 | 120 | 1206W4F1200T5E (UNI-ROYAL) | C17909 | Basic | 475,116 | 2026-09-06 |
| JP1, JP2 | 1x2 header | PZ254V-11-02P (XFCN) | C492401 | Extended | 1,279,800 | 2026-09-06 |
| D20 | PESD1CAN | PESD1CAN,215 (Nexperia) | C15771 | Extended | 279,780 | 2026-09-06 |
| U9 | TJA1027T/20 | TJA1027T/20,118 (NXP) | C112994 | Extended | 2,196 | 2026-09-06 |
| R42 | 510 0.5W | FRC2512J511TS (FOJAN) | C2934121 | Extended | 30,852 | 2026-09-06 |
| D21 | SMAJ24A | SMAJ24A (Littelfuse) | C148222 | Extended | 25,930 | 2026-09-06 |

### Substitutions made this task (Task 10)

- **D1** `SMDJ18A` (Littelfuse) is not listed on lcsc.com/JLCPCB at all. Substituted
  DOWO `5.0SMDJ18A` (C284071): same SMC(DO-214AB) package, same 18V standoff voltage,
  3000W-class TVS. `mfr` changed Littelfuse -> DOWO.
- **D2** `BAT54W` (Nexperia, C8657) is out of stock. Substituted JSCJ's `BAT54W`
  (C77328), same SOT-323 package, LCSC describes it as "1 Independent" (single diode),
  which matches this design's pin-2-NC single-diode use better than Nexperia's own
  dual-diode BAT54W/AW/CW/SW family. `mfr` changed Nexperia -> JSCJ.
- **L1** Bourns `SRN6045TA-6R8M` (C2041457) has 1 unit in stock. Substituted YJYCOIN
  `YNR6045-6R8M` (C341066): identical 6.8uH / SMD 6x6mm / 3A shielded spec, same "6045"
  case as the Bourns part the footprint is named for. `mpn`/`mfr` filled in (were empty).
- **J5** microSD: the real Hirose `DM3BT-DSF-PEJS` is itself on LCSC as C597972 (1,271
  in stock) - the exact part the KiCad footprint is named for, so no substitution was
  needed. (This is a better source than the old board's SHOU HAN "TF PUSH" clone,
  C393941, which is only 8 contacts with no separate card-detect pins.)

### Resolved concerns (controller rulings, fix round after Task 10)

1. **U3 `AP63200WU-7`** (C2071868, Diodes Inc): lcsc.com's retail storefront page shows
   "Out of Stock", but the JLC parts mirror (jlcsearch.tscircuit.com) shows this same
   LCSC code has 2,599 units available for SMT assembly - LCSC's retail stock and
   JLCPCB's assembly-reel stock are separate pools, and assembly is what matters for
   this board. **Controller ruling: keep C2071868.** Fallback recorded above
   (`TPS54302DDCR`, C311983) if assembly stock is actually empty at order time - not
   applied, needs an FB divider (80.6k/10k for 5.4V against its 0.596V reference), an
   EN divider, and redrawing U3's pinout (its symbol pins differ from AP63200WU).
2. **U2 `BTS7002-1EPP`**: `C534824` (used in the original Task 10 pass) 404s on
   lcsc.com because it isn't the live JLC listing for this part. The JLC parts mirror
   (`jlcsearch.tscircuit.com/api/search?q=BTS7002-1EPP`) resolves it to **LCSC
   `C2680407`** (mfr code `BTS70021EPPXUMA1`, TSSOP-14-EP package, 273 in stock,
   $3.77). **Controller ruling: set `U2.lcsc = "C2680407"`, `mpn =
   "BTS70021EPPXUMA1"`.** Fallback recorded above (`BTS7004-1EPP`, C534825, same
   TSDSO-14 package/pinout, 4.4mOhm/15A, 3,100 in stock) if 7002 is out at order time.
3. **J6 / D20 stock**: `B4B-XH-A(LF)(SN)` (C144395, 611 units) and the rest are fine
   for a small hobby-quantity JLCPCB order but are thin; re-check before a larger run.
   (Still open, not part of the controller rulings above.)
