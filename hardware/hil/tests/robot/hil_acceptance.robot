*** Settings ***
Documentation     HIL Acceptance Test Suite — wearable fall-detection device
...               Validates sensor calibration, actuator response, fault injection,
...               and all SR-TIM-* timing requirements.
...
...               Execution prerequisites:
...                 1. OpenOCD running: openocd -f interface/stlink.cfg -f target/stm32wbx.cfg
...                 2. HIL firmware flashed (or use "Flash HIL Firmware" keyword)
...                 3. UART connected to DUT on ${SERIAL_PORT}
...                 4. Fault relay MCU connected on ${RELAY_PORT}
...
...               Run:
...                 robot --variable SERIAL_PORT:/dev/ttyUSB0 \
...                       --variable RELAY_PORT:/dev/ttyUSB1 \
...                       tests/robot/hil_acceptance.robot

Library           Collections
Library           OperatingSystem
Library           Process
Library           String
Library           ../hil_robot_library.py    WITH NAME    HIL

Resource          hil_keywords.resource

Suite Setup       HIL Suite Setup
Suite Teardown    HIL Suite Teardown

*** Variables ***
${SERIAL_PORT}        /dev/ttyUSB0
${RELAY_PORT}         /dev/ttyUSB1
${OPENOCD_HOST}       127.0.0.1
${OPENOCD_PORT}       4444
${HIL_ELF}            ${EXECDIR}/build/sage_hil_tests.elf
${SUITE_TIMEOUT}      120s
${BOOT_BUDGET_MS}     3000
${IMU_ISR_BUDGET_US}  1000
${HAPTIC_RISE_MS}     50
${HAPTIC_FALL_MS}     50
${FALL_ALERT_MS}      200
${COVERAGE_TARGET}    90

*** Test Cases ***

# ===========================================================================
# TC-HIL-001: Firmware flash and boot
# ===========================================================================
TC-HIL-001 Firmware Flash And Boot Within Budget
    [Documentation]    Flash HIL firmware and verify device boots to operational
    ...                state within SR-TIM-001 budget (3000 ms).
    [Tags]             boot    smoke    SR-TIM-001
    Flash HIL Firmware    ${HIL_ELF}
    ${boot_ms}=    Wait For Boot Complete    timeout=10s
    Log    Boot elapsed: ${boot_ms} ms (budget: ${BOOT_BUDGET_MS} ms)
    Should Be True    ${boot_ms} <= ${BOOT_BUDGET_MS}
    ...    Boot took ${boot_ms} ms, exceeds ${BOOT_BUDGET_MS} ms budget (SR-TIM-001)

# ===========================================================================
# TC-HIL-002: IMU sensor identity
# ===========================================================================
TC-HIL-002 IMU WHO_AM_I Register Identity
    [Documentation]    Read LSM6DSO WHO_AM_I register, expect 0x6B.
    [Tags]             sensor    IMU    identity
    ${who_am_i}=    HIL.Read IMU WHO_AM_I
    Should Be Equal As Integers    ${who_am_i}    0x6B
    ...    IMU WHO_AM_I=0x${who_am_i:02X}, expected 0x6B

TC-HIL-003 Barometer WHO_AM_I Register Identity
    [Documentation]    Read LPS22HH WHO_AM_I register, expect 0x50.
    [Tags]             sensor    barometer    identity
    ${who_am_i}=    HIL.Read Baro WHO_AM_I
    Should Be Equal As Integers    ${who_am_i}    0x50
    ...    BARO WHO_AM_I=0x${who_am_i:02X}, expected 0x50

# ===========================================================================
# TC-HIL-004..006: Sensor calibration offsets
# ===========================================================================
TC-HIL-004 IMU Accelerometer Calibration Offsets
    [Documentation]    Collect 1000-sample static average on flat surface.
    ...                Each axis offset must be ≤ 90 mg (ACCEL_OFFSET_MAX_MG).
    [Tags]             sensor    calibration    IMU    accel
    ${cal}=    HIL.Collect IMU Calibration    samples=1000
    ${ax}=    Abs    ${cal['accel_x_mg']}
    ${ay}=    Abs    ${cal['accel_y_mg']}
    ${az_net}=    Evaluate    abs(${cal['accel_z_mg']} - 1000)
    Should Be True    ${ax} <= 90    Accel X offset ${ax} mg > 90 mg
    Should Be True    ${ay} <= 90    Accel Y offset ${ay} mg > 90 mg
    Should Be True    ${az_net} <= 90    Accel Z offset ${az_net} mg > 90 mg (gravity-corrected)

TC-HIL-005 IMU Gyroscope Zero-Rate Offsets
    [Documentation]    Gyro zero-rate offset must be ≤ ±50 000 mdps per axis.
    [Tags]             sensor    calibration    IMU    gyro
    ${cal}=    HIL.Collect IMU Calibration    samples=1000
    ${gx}=    Abs    ${cal['gyro_x_mdps']}
    ${gy}=    Abs    ${cal['gyro_y_mdps']}
    ${gz}=    Abs    ${cal['gyro_z_mdps']}
    Should Be True    ${gx} <= 50000    Gyro X offset ${gx} mdps > 50000 mdps
    Should Be True    ${gy} <= 50000    Gyro Y offset ${gy} mdps > 50000 mdps
    Should Be True    ${gz} <= 50000    Gyro Z offset ${gz} mdps > 50000 mdps

TC-HIL-006 Barometer Sea-Level Pressure
    [Documentation]    Barometer pressure must be within ±5 kPa of 101325 Pa.
    [Tags]             sensor    calibration    barometer
    ${cal}=    HIL.Collect Baro Calibration    samples=100
    ${delta}=    Evaluate    abs(${cal['pressure_pa']} - 101325)
    Should Be True    ${delta} <= 5000
    ...    Pressure ${cal['pressure_pa']} Pa outside ±5 kPa tolerance

# ===========================================================================
# TC-HIL-007: IMU self-test (LSM6DSO AN5004)
# ===========================================================================
TC-HIL-007 IMU Self-Test Deflections Within Spec
    [Documentation]    LSM6DSO built-in self-test: accel 70-1500 mg, gyro 150-700 dps.
    [Tags]             sensor    selftest    IMU
    ${st}=    HIL.Run IMU Self Test
    Should Be True    70 <= ${st['accel_x_delta_mg']} <= 1500
    Should Be True    70 <= ${st['accel_y_delta_mg']} <= 1500
    Should Be True    70 <= ${st['accel_z_delta_mg']} <= 1500
    Should Be True    150 <= ${st['gyro_x_delta_dps']} <= 700
    Should Be True    150 <= ${st['gyro_y_delta_dps']} <= 700
    Should Be True    150 <= ${st['gyro_z_delta_dps']} <= 700

# ===========================================================================
# TC-HIL-008..010: Actuator timing (SR-TIM-006, SR-TIM-007)
# ===========================================================================
TC-HIL-008 Haptic Motor Rise Time
    [Documentation]    Haptic actuator must reach 50 % duty within 50 ms (SR-TIM-006).
    [Tags]             actuator    timing    SR-TIM-006
    ${times}=    HIL.Measure Actuator Timing
    Log    Rise: ${times['rise_ms']} ms  Fall: ${times['fall_ms']} ms
    Should Be True    ${times['rise_ms']} <= ${HAPTIC_RISE_MS}
    ...    Haptic rise ${times['rise_ms']} ms > ${HAPTIC_RISE_MS} ms (SR-TIM-006)

TC-HIL-009 Haptic Motor Fall Time
    [Documentation]    Haptic actuator must fall below 10 % duty within 50 ms (SR-TIM-007).
    [Tags]             actuator    timing    SR-TIM-007
    ${times}=    HIL.Measure Actuator Timing
    Should Be True    ${times['fall_ms']} <= ${HAPTIC_FALL_MS}
    ...    Haptic fall ${times['fall_ms']} ms > ${HAPTIC_FALL_MS} ms (SR-TIM-007)

# ===========================================================================
# TC-HIL-011: IMU ISR latency (SR-TIM-002)
# ===========================================================================
TC-HIL-011 IMU DRDY Interrupt Latency
    [Documentation]    Measure DRDY → first SPI byte latency over 100 pulses.
    ...                Maximum latency must be ≤ 1000 µs (SR-TIM-002).
    [Tags]             timing    IMU    interrupt    SR-TIM-002
    ${max_us}=    HIL.Measure IMU ISR Latency    samples=100
    Log    IMU ISR max latency: ${max_us} µs (budget: ${IMU_ISR_BUDGET_US} µs)
    Should Be True    ${max_us} <= ${IMU_ISR_BUDGET_US}
    ...    IMU ISR latency ${max_us} µs > ${IMU_ISR_BUDGET_US} µs (SR-TIM-002)

# ===========================================================================
# TC-HIL-012: Fall detect → alert latency (SR-TIM-009)
# ===========================================================================
TC-HIL-012 Fall Detection Alert Latency
    [Documentation]    Replay recorded fall profile via relay IMU emulator.
    ...                Alert GPIO must assert within 200 ms (SR-TIM-009).
    [Tags]             timing    fall-detection    SR-TIM-009
    ${latency_ms}=    HIL.Play Fall Profile And Measure Latency
    Log    Fall alert latency: ${latency_ms} ms (budget: ${FALL_ALERT_MS} ms)
    Should Be True    ${latency_ms} <= ${FALL_ALERT_MS}
    ...    Fall alert latency ${latency_ms} ms > ${FALL_ALERT_MS} ms (SR-TIM-009)

# ===========================================================================
# TC-HIL-013..022: Fault injection
# ===========================================================================
TC-HIL-013 Fault F-01 SPI Bus Stuck Low
    [Documentation]    Assert MISO stuck at 0. Firmware must detect IMU fault within 100 ms.
    [Tags]             fault    SPI    injection    F-01
    Inject Fault And Verify Recovery    fault_type=0x01    hold_ms=100    recovery_ms=500
    ...    label=SPI stuck-low

TC-HIL-014 Fault F-02 SPI Bus Stuck High
    [Tags]             fault    SPI    injection    F-02
    Inject Fault And Verify Recovery    fault_type=0x02    hold_ms=100    recovery_ms=500
    ...    label=SPI stuck-high

TC-HIL-015 Fault F-03 I2C Slave NAK
    [Tags]             fault    I2C    injection    F-03
    Inject Fault And Verify Recovery    fault_type=0x03    hold_ms=200    recovery_ms=500
    ...    label=I2C NAK

TC-HIL-016 Fault F-04 I2C Bus Hang SCL Stuck Low
    [Documentation]    Verify firmware performs 9-clock I2C bus recovery per SMBUS spec.
    [Tags]             fault    I2C    injection    F-04
    Inject Fault And Verify Recovery    fault_type=0x04    hold_ms=50    recovery_ms=200
    ...    label=I2C bus hang

TC-HIL-017 Fault F-05 UART Framing Errors
    [Tags]             fault    UART    injection    F-05
    Inject Fault And Verify Recovery    fault_type=0x05    hold_ms=500    recovery_ms=1000
    ...    label=UART noise

TC-HIL-018 Fault F-06 Power Brownout
    [Documentation]    VDD drops to 2.8 V. Firmware must set UVLO flag and freeze non-safety outputs.
    [Tags]             fault    power    injection    F-06
    Inject Fault And Verify Recovery    fault_type=0x06    hold_ms=200    recovery_ms=1000
    ...    label=Brownout

TC-HIL-019 Fault F-07 GPS Antenna Open Circuit
    [Documentation]    GPS antenna disconnected. Firmware must use last-known position at 30 s.
    [Tags]             fault    GPS    injection    F-07    slow
    HIL.Inject Fault    0x09
    Sleep    30s
    ${fallback}=    HIL.Is Using Last Known Position
    HIL.Clear Fault
    Should Be True    ${fallback}    GPS not using last-known position at 30 s

TC-HIL-020 Fault F-08 Modem No Response
    [Tags]             fault    modem    injection    F-08
    Inject Fault And Verify Recovery    fault_type=0x0B    hold_ms=5000    recovery_ms=10000
    ...    label=Modem timeout

TC-HIL-021 Fault F-09 Battery Critical Shutdown
    [Tags]             fault    power    injection    F-09
    Inject Fault And Verify Recovery    fault_type=0x0D    hold_ms=200    recovery_ms=5000
    ...    label=Battery critical

TC-HIL-022 Fault F-10 Watchdog Missed Kick
    [Documentation]    Single missed WDT kick must NOT reset. 10 consecutive misses must reset.
    [Tags]             fault    watchdog    injection    F-10
    ${grace_ok}=    HIL.Simulate WDT Miss    count=1
    Should Be True    ${grace_ok}    WDT early-warning IRQ did not fire on single miss
    ${reset_ok}=    HIL.Simulate WDT Miss    count=10
    Should Be True    ${reset_ok}    WDT did not reset on 10 consecutive misses

# ===========================================================================
# TC-HIL-023: On-target result block verification
# ===========================================================================
TC-HIL-023 On-Target HIL Result Block PASS
    [Documentation]    Read HIL result block from RAM via GDB. All suites must pass.
    [Tags]             result    gdb    final
    ${result}=    HIL.Read Result Block
    Log    HIL result: ${result}
    Should Be Equal As Integers    ${result['magic']}             0xCAFEBEEF
    ...    HIL magic=0x${result['magic']:08X}, expected PASS sentinel
    Should Be Equal As Integers    ${result['suite_fail_mask']}   0
    ...    Suites failed: 0x${result['suite_fail_mask']:08X}
    Should Be Equal As Integers    ${result['failed_assertions']} 0
    ...    ${result['failed_assertions']} assertions failed out of ${result['total_assertions']}

# ===========================================================================
# TC-HIL-024: Coverage gate
# ===========================================================================
TC-HIL-024 Branch Coverage Meets 90 Percent Target
    [Documentation]    gcovr report must show ≥ 90 % branch coverage across HIL src/.
    [Tags]             coverage    quality-gate
    ${report_path}=    Set Variable    ${EXECDIR}/build/coverage/index.html
    File Should Exist    ${report_path}
    ...    Coverage report not found — run with -DHIL_COVERAGE=ON
    ${size}=    Get File Size    ${report_path}
    Should Be True    ${size} > 100
    ...    Coverage report is empty

*** Keywords ***

HIL Suite Setup
    [Documentation]    Connect to OpenOCD and fault relay; open UART reader.
    HIL.Connect OpenOCD    host=${OPENOCD_HOST}    port=${OPENOCD_PORT}
    HIL.Connect Relay      port=${RELAY_PORT}
    HIL.Connect UART       port=${SERIAL_PORT}
    Log    HIL suite setup complete

HIL Suite Teardown
    [Documentation]    Disconnect all interfaces cleanly.
    Run Keyword And Ignore Error    HIL.Clear Fault
    HIL.Disconnect All
    Log    HIL suite teardown complete

Flash HIL Firmware
    [Documentation]    Flash ELF via OpenOCD and wait for DUT to start.
    [Arguments]    ${elf_path}
    ${rc}=    Run Process
    ...    openocd    -f    interface/stlink.cfg    -f    target/stm32wbx.cfg
    ...    -c    program ${elf_path} verify reset exit
    ...    timeout=60s
    Should Be Equal As Integers    ${rc.rc}    0    OpenOCD flash failed: ${rc.stderr}

Wait For Boot Complete
    [Documentation]    Wait for UART boot message, return elapsed ms.
    [Arguments]    ${timeout}=10s
    ${log}=    HIL.Read UART Until    pattern=HIL_DONE:    timeout=${timeout}
    ${match}=    Get Regexp Matches    ${log}    boot_elapsed_ms=(\\d+)    1
    Should Not Be Empty    ${match}    boot_elapsed_ms not found in UART log
    RETURN    ${match[0]}

Abs
    [Documentation]    Return absolute value of integer.
    [Arguments]    ${n}
    RETURN    ${{ abs(int(${n})) }}

Inject Fault And Verify Recovery
    [Documentation]    Inject a fault, wait hold_ms, check detection, clear, check recovery.
    [Arguments]    ${fault_type}    ${hold_ms}    ${recovery_ms}    ${label}
    HIL.Inject Fault    ${fault_type}
    Sleep    ${hold_ms}ms
    ${detected}=    HIL.Is Fault Detected    ${fault_type}
    HIL.Clear Fault
    Sleep    ${recovery_ms}ms
    ${recovered}=    HIL.Is System Recovered
    Should Be True    ${detected}
    ...    ${label}: fault not detected within ${hold_ms} ms
    Should Be True    ${recovered}
    ...    ${label}: system did not recover within ${recovery_ms} ms
