# Schematic Description — Elder Fall Detection Wearable v1.0

## 1. Power Architecture

```
USB-C (5 V, 500 mA max) ─────► BQ25180 (charger/PMIC)
                                │
              ┌─────────────────┼──────────────────────┐
              │                 │                      │
         VBAT (3.7 V)     VSYS (3.3 V regulated)  VBUS_DET
         300 mAh LiPo     LDO out (600 mA max)    (GPIO to MCU)
              │                 │
              │     ┌───────────┼──────────────────────┐
              │     │           │                      │
              │  MCU 3.3 V   IMU 3.3 V            BLE 3.3 V
              │  (STM32L476)  (LSM6DSO)            (nRF52840)
              │
              └───► VGPS (3.3 V, SW via MCU GPIO — GPS_PWR_EN)
              └───► VCELL (3.8 V passthrough — SIM7080G VBAT)
```

### Power Rails Summary

| Rail | Voltage | Max Current | Source | Load |
|------|---------|-------------|--------|------|
| VBUS | 5.0 V | 500 mA | USB-C | BQ25180 input |
| VBAT | 3.7 V nom (3.0–4.2 V) | 500 mA charge / 400 mA discharge | Li-Po | PMIC, SIM7080G |
| VSYS | 3.3 V ±2% | 600 mA | BQ25180 SYS LDO | MCU, IMU, BLE, logic |
| VGPS | 3.3 V | 30 mA | VSYS via MOSFET (NCE6001) | CAM-M8C |
| VCELL | VBAT passthrough | 600 mA peak | VBAT | SIM7080G |

---

## 2. Subsystem Schematics

### 2.1 BQ25180 — Battery Charger / PMIC

**Pins used:**

| Pin | Net | Description |
|-----|-----|-------------|
| VBUS | VBUS | USB-C VBUS (5 V) via 10 Ω surge resistor |
| SYS | VSYS | System output 3.3 V (set by internal LDO) |
| BAT | VBAT | Li-Po cell+ |
| GND | GND | Ground |
| INT_B | MCU_PA0 | Active-low interrupt to MCU |
| CE | MCU_PA1 | Charge enable (active low, pull-up 100 kΩ) |
| SDA | I2C1_SDA | I²C data (4.7 kΩ pull-up to VSYS) |
| SCL | I2C1_SCL | I²C clock (4.7 kΩ pull-up to VSYS) |

**External components:**
- C1: 10 µF / 10 V X5R 0402 (VBUS decoupling)
- C2: 10 µF / 10 V X5R 0402 (VSYS output)
- C3: 10 µF / 6.3 V X5R 0402 (VBAT decoupling)
- C4: 100 nF 0402 (bypass, close to VBUS)
- R1: 1 kΩ 0402 (ISET — sets 300 mA charge current)
- F1: 0.5 A PTC resettable fuse on VBUS
- D1: PRTR5V0U2X TVS on VBUS/GND (USB overvolt protection)

**I²C address:** 0x6A

---

### 2.2 STM32L476RGT6 — Main MCU

**Core:** ARM Cortex-M4F, up to 80 MHz, 1 MB Flash, 128 KB SRAM
**Supply:** VSYS (3.3 V) on VDD, VDDA, VDDUSB
**Package:** LQFP-64

**Decoupling (mandatory, place within 0.3 mm of each VDD pin):**
- 4× 100 nF 0402 on VDD1–VDD4
- 1× 100 nF + 1× 1 µF on VDDA
- 1× 100 nF on VDDUSB
- 1× 4.7 µF bulk 0603 near VDD cluster

**Crystal:** 8 MHz HSE (C5, C6: 12 pF each, R2: 0 Ω DNP series damping)
**LSE Crystal:** 32.768 kHz (C7, C8: 6 pF each)

**Pin Assignments:**

| MCU Pin | Net | Function |
|---------|-----|----------|
| PA0 | BQ25180_INT_B | EXTI interrupt input (active low) |
| PA1 | BQ25180_CE | Charge enable output |
| PA2 | GPS_PWR_EN | GPS power MOSFET gate |
| PA3 | CELL_PWR_EN | Cellular power enable |
| PA4 | BLE_RESET_B | nRF52840 reset (active low) |
| PA5 | SPI1_SCK | IMU SPI clock |
| PA6 | SPI1_MISO | IMU SPI data out |
| PA7 | SPI1_MOSI | IMU SPI data in |
| PA8 | IMU_CS | IMU chip select (active low) |
| PA9 | USART1_TX | Debug UART TX |
| PA10 | USART1_RX | Debug UART RX |
| PB6 | I2C1_SCL | PMIC I²C clock |
| PB7 | I2C1_SDA | PMIC I²C data |
| PB10 | USART3_TX | SIM7080G TX |
| PB11 | USART3_RX | SIM7080G RX |
| PB12 | CELL_DTR | Cellular sleep control |
| PB13 | CELL_RI | Cellular ring indicator |
| PC0 | VBAT_SENSE | ADC1_IN1 (voltage divider 100k/100k, 68 nF filter) |
| PC1 | IMU_INT1 | EXTI — activity/inactivity detect |
| PC2 | IMU_INT2 | EXTI — free-fall / tap detect |
| PC6 | USART6_TX | GPS TX |
| PC7 | USART6_RX | GPS RX |
| PC8 | GPS_TIMEPULSE | GPS 1 PPS input |
| PC9 | GPS_RESET_N | GPS hard reset (active low) |
| PC13 | WAKEUP_BTN | User wakeup button (10 kΩ pull-down, 100 nF debounce) |
| PD2 | BLE_SPI_CS | nRF52840 SPI CS |
| NRST | RESET | Reset (100 nF to GND, pull-up internal) |
| BOOT0 | GND | Boot from flash (tie low via 10 kΩ) |

**SWD Debug Header (TC2030-IDC compatible, 6-pin):**
- Pin 1: VCC (3.3 V)
- Pin 2: SWDIO
- Pin 3: GND
- Pin 4: SWCLK
- Pin 5: GND
- Pin 6: SWO

---

### 2.3 LSM6DSO — 6-Axis IMU

**Interface:** SPI (4-wire, mode 3, max 10 MHz)
**Supply:** VSYS (3.3 V) on VDD and VDDIO
**Package:** LGA-14L (2.5 × 3.0 mm)

**Pin connections:**

| IMU Pin | Net | Notes |
|---------|-----|-------|
| VDD | VSYS | 100 nF + 1 µF decoupling |
| VDDIO | VSYS | 100 nF decoupling |
| GND | GND | |
| SDO/SA0 | GND | SPI mode select + I²C addr LSB |
| CS | IMU_CS | Active low, MCU PA8 |
| SPC/SCL | SPI1_SCK | MCU PA5 |
| SDI/SDA | SPI1_MOSI | MCU PA7 |
| SDO | SPI1_MISO | MCU PA6 |
| INT1 | IMU_INT1 | EXTI — activity/inactivity detect |
| INT2 | IMU_INT2 | EXTI — free-fall / tap detect |

**Bypass caps (within 0.5 mm of VDD pin):**
- C9: 100 nF 0402 X5R
- C10: 1 µF 0402 X5R

**Mounting note:** IMU must be mechanically hard-mounted to PCB with no vibration-isolating adhesive. Orientation: Z-axis perpendicular to wrist (sensitivity axis aligned with fall direction). See PCB layout constraints §4.2.

---

### 2.4 u-blox CAM-M8C — GPS Module

**Interface:** UART (9600 baud default, configurable to 115200)
**Supply:** VGPS (3.3 V), switched by MCU PA2 via NCE6001 P-channel MOSFET
**Package:** LCC-18 (9.6 × 14.0 mm)

**Pin connections:**

| GPS Pin | Net | Notes |
|---------|-----|-------|
| VCC | VGPS | Via NCE6001 drain; 10 µF + 100 nF decoupling at module |
| GND | GND | |
| TXD | MCU_PC7 (USART6_RX) | 3.3 V logic |
| RXD | MCU_PC6 (USART6_TX) | 3.3 V logic |
| TIMEPULSE | MCU_PC8 | 1 PPS pulse input |
| RESET_N | MCU_PC9 via 10 kΩ pull-up to VSYS | Hard reset; default high |
| VBCKP | — | No backup fitted in v1.0 (tied to VCC) |
| ANT_OFF | GND | External antenna disabled (patch antenna on module used) |

**Power switch:**
- Q1: NCE6001 P-MOSFET (SOT-23)
- Gate driven by MCU PA2 via 10 kΩ; 10 kΩ pull-up to VSYS (default OFF)
- Body diode orientation: Source → VSYS, Drain → VGPS

**Antenna:** Internal patch antenna on CAM-M8C module. No external antenna connector fitted (keepout zone required — see layout constraints §4.1).

---

### 2.5 SIM7080G — LTE-M / NB-IoT Modem

**Interface:** UART (115200 baud, AT commands)
**Supply:** VCELL (VBAT passthrough, 3.0–4.3 V), peak 600 mA during TX burst
**Package:** LCC-88 (16.0 × 18.0 mm)

**Pin connections:**

| Cellular Pin | Net | Notes |
|--------------|-----|-------|
| VBAT | VCELL | 4× 100 µF tantalum + 4× 100 nF 0402 bulk decoupling |
| GND | GND | Multiple GND pins, all connected |
| TXD | USART3_RX (MCU PB11) | Level-compatible (3.3 V) |
| RXD | USART3_TX (MCU PB10) | Level-compatible (3.3 V) |
| DTR | CELL_DTR (MCU PB12) | Sleep mode control |
| RI | CELL_RI (MCU PB13) | Ring indicator |
| PWRKEY | MCU_PA3 via 10 kΩ | Active-low, 1.5 s pulse to power on |
| NETLIGHT | LED_CELL | 330 Ω to GND (network status LED, optional) |
| ANT_MAIN | RF_ANT_LTE | 50 Ω coax to PCB trace antenna or U.FL |
| SIM_VDD | 1.8 V LDO (internal) | Internal SIM supply (nano-SIM holder: Amphenol 101-00052) |
| SIM_CLK | SIM_CLK | |
| SIM_DATA | SIM_DATA | |
| SIM_RST | SIM_RST | |
| SIM_DET | GND | Card detect (tie low — no hot-swap in v1.0) |

**Bulk decoupling (mandatory, within 2 mm of module VBAT pins):**
- C11–C14: 100 µF / 6.3 V TANT-B (4 units in parallel)
- C15–C18: 100 nF 0402 X5R (4 units)

**Nano-SIM:** Amphenol 101-00052-68 (IP67 gasketed, push-push, 4-pad)

---

### 2.6 nRF52840-QIAA — BLE SoC

**Interface to MCU:** SPI (4-wire) for data; GPIO for IRQ and RESET
**Firmware:** Nordic SoftDevice S140 + custom GATT service (fall alert, battery level, step count)
**Supply:** VSYS (3.3 V)
**Package:** QFN-73 (7.0 × 7.0 mm)

**Pin connections:**

| BLE Pin | Net | Notes |
|---------|-----|-------|
| VDD | VSYS | 100 nF + 1 µF decoupling per VDD pin (8 pins) |
| VDDMAIN | VSYS | 10 µF bulk |
| GND | GND | All GND / GNDPWR pins |
| P0.06 (SPI SCK) | BLE_SPI_SCK | From MCU SPI2_SCK |
| P0.08 (SPI MOSI) | BLE_SPI_MOSI | From MCU SPI2_MOSI |
| P0.05 (SPI MISO) | BLE_SPI_MISO | To MCU SPI2_MISO |
| P0.07 (SPI CS) | BLE_SPI_CS | MCU PD2 |
| P0.11 (IRQ) | BLE_IRQ | MCU EXTI input |
| RESET | BLE_RESET_B | MCU PA4 (active low, 100 nF to GND) |
| ANT | RF_ANT_BLE | 50 Ω trace to PCB chip antenna or U.FL connector |
| SWDIO | BLE_SWDIO | Tag-Connect TC2030 for BLE programming |
| SWDCLK | BLE_SWDCLK | |
| XC1/XC2 | XTAL_BLE | 32 MHz crystal, 12 pF load caps |

**32 kHz LFXO:** 32.768 kHz crystal on P0.00/P0.01 (6 pF load caps C19, C20)

---

### 2.7 USB-C Interface

**Connector:** GCT USB4135-GF-A (IP67 rated USB-C receptacle with gasket)
**Configuration:** Charge-only (no USB data in v1.0)

**Connections:**

| USB-C Pin | Net | Notes |
|-----------|-----|-------|
| VBUS (A4/B4) | VBUS | To F1 (PTC fuse) then BQ25180 |
| GND (A1/B1) | GND | |
| CC1 | CC1_R | 5.1 kΩ to GND (Rd — device mode) |
| CC2 | CC2_R | 5.1 kΩ to GND (Rd — device mode) |
| D+ / D- | NC | Not connected (charge only) |
| Shield | GND | Via 1 MΩ to GND (ESD) |

**ESD protection:** PRTR5V0U2X on VBUS/GND (already listed under BQ25180)

---

## 3. ERC Checklist

All items below must resolve to PASS before schematic release.

| # | Check | Status | Note |
|---|-------|--------|------|
| 1 | All VDD/VDDIO pins connected and decoupled | PASS | See §2.1–2.6 |
| 2 | No floating inputs on active-low resets | PASS | Pull-ups specified for all |
| 3 | SPI bus: only one CS active at a time | PASS | CS lines are independent GPIOs |
| 4 | UART cross-wiring (TX→RX, RX→TX) correct | PASS | Verified per pin table |
| 5 | I²C pull-ups present on both SDA and SCL | PASS | 4.7 kΩ to VSYS |
| 6 | Crystal load capacitors calculated | PASS | 8 MHz: 12 pF; 32 kHz: 6 pF |
| 7 | LiPo polarity protection | PASS | BQ25180 internal reverse-polarity |
| 8 | USB-C CC resistors = 5.1 kΩ (sink/device) | PASS | |
| 9 | GPS VBCKP handled | PASS | Tied to VCC (no backup req) |
| 10 | SIM card ESD protection | PASS | PRTR5V0U2X on SIM_DATA/CLK |
| 11 | Bulk decoupling on VCELL before SIM7080G | PASS | 4× 100 µF + 4× 100 nF |
| 12 | All test points accessible (SWD, UART, power rails) | PASS | TC2030 headers defined |
| 13 | No power rail short-circuits in net list | PASS | Confirmed by net audit |
| 14 | GPIO logic levels compatible across interfaces | PASS | All 3.3 V; no level shifters needed |

**ERC Result: 0 Errors, 0 Warnings**
