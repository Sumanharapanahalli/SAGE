*** Settings ***
Documentation     HIL Acceptance Suite — Intersection Collision-Warning Firmware
...
...               Scenario under test (task payload):
...                 "Intersection with vehicle A — collision warning triggered
...                  when vehicle A approaches intersection."
...
...               Acceptance criteria:
...                 AC-HIL-CW-001 : HIL test coverage ≥ 90 % (SR-COV-001)
...                 AC-HIL-CW-002 : All fault injection tests pass
...                 AC-HIL-CW-003 : Timing requirements verified (SR-CW-TIM-*)
...
...               Execution prerequisites:
...                 1. OpenOCD running:
...                    openocd -f interface/stlink.cfg -f target/stm32wbx.cfg
...                 2. HIL firmware flashed:
...                    cmake --build build && make -C build flash
...                 3. UART semihosting log connected on ${SERIAL_PORT}
...
...               Run:
...                 robot --variable SERIAL_PORT:/dev/ttyUSB0 \\
...                       --variable OPENOCD_HOST:127.0.0.1 \\
...                       --variable OPENOCD_PORT:4444 \\
...                       tests/robot/intersection_collision_warning.robot

Library           Collections
Library           OperatingSystem
Library           Process
Library           String
Library           ../hil_robot_library.py    WITH NAME    HIL
Library           ../intersection_scenario_runner.py    WITH NAME    IS

Resource          hil_keywords.resource

Suite Setup       Intersection Suite Setup
Suite Teardown    Intersection Suite Teardown
Test Setup        Reset Radar Stubs And Faults
Test Teardown     Reset Radar Stubs And Faults

*** Variables ***
${SERIAL_PORT}              /dev/ttyUSB0
${OPENOCD_HOST}             127.0.0.1
${OPENOCD_PORT}             4444
${HIL_ELF}                  ${EXECDIR}/build/sage_hil_tests.elf
${REPORT_JSON}              ${EXECDIR}/results/intersection_report.json

# Sensor IDs (must match CW_SENSOR_* in collision_warning_hal.h)
${SENSOR_FRONT_LEFT}        0
${SENSOR_FRONT_RIGHT}       1
${SENSOR_REAR_LEFT}         2
${SENSOR_REAR_RIGHT}        3

# Warning levels (must match CW_WarningLevel_t)
${WARN_NONE}                0
${WARN_ADVISORY}            1
${WARN_CAUTION}             2
${WARN_CRITICAL}            3

# Timing budgets (milliseconds)
${DETECTION_LATENCY_MAX}    50
${WARNING_LATENCY_MAX}      100
${POLL_PERIOD_MS}           10
${POLL_JITTER_MS}           1

# Thresholds
${COVERAGE_TARGET_PCT}      90
${SETTLE_MS}                30

*** Test Cases ***

# ===========================================================================
# TC-IS-001: Vehicle A approaches intersection — CRITICAL warning triggered
# Scenario : IS-SCN-001 — T-junction, FRONT_LEFT, 1 m/s
# ===========================================================================
TC-IS-001 Vehicle A Triggers CRITICAL Warning At Intersection
    [Documentation]    Vehicle A approaches on FRONT_LEFT at 1 m/s from 10 m.
    ...                System must issue CRITICAL when distance ≤ 200 cm.
    ...                Verifies: AC-HIL-CW-002, AC-HIL-CW-003 (SR-CW-TIM-001/002)
    [Tags]             intersection    vehicle-a    critical    smoke
    ...                SR-CW-TIM-001    SR-CW-TIM-002    AC-HIL-CW-002

    # Inject Vehicle A approach profile: 1000 → 200 cm in 8 steps, 1 m/s
    ${profile}=    Create List
    ...    1000    900    800    700    600    500    400    200

    ${states}=    IS.Approach Profile
    ...    sensor_id=${SENSOR_FRONT_LEFT}
    ...    profile_cm=${profile}
    ...    vel_cms=-100
    ...    step_ms=${15}

    ${final}=    Get From List    ${states}    -1

    Log    Final warning level: ${final.level} (${final.level_name()})
    Log    TTC: ${final.ttc_ms} ms
    Log    Detection latency: ${final.detection_lat_ms} ms
    Log    Warning output latency: ${final.warning_lat_ms} ms

    Should Be Equal As Integers    ${final.level}    ${WARN_CRITICAL}
    ...    Expected CRITICAL (${WARN_CRITICAL}), got level=${final.level} at 200 cm
    ...    (AC-HIL-CW-002: collision warning triggered for vehicle A)

TC-IS-002 Vehicle A Warning Escalates Monotonically
    [Documentation]    Warning level must escalate NONE→ADVISORY→CAUTION→CRITICAL.
    ...                Level must never de-escalate during vehicle approach.
    [Tags]             intersection    vehicle-a    escalation

    ${profile}=    Create List    1000    900    800    700    600    500    400    200
    ${states}=    IS.Approach Profile
    ...    sensor_id=${SENSOR_FRONT_LEFT}    profile_cm=${profile}
    ...    vel_cms=-100    step_ms=${15}

    ${levels}=    Create List
    FOR    ${s}    IN    @{states}
        Append To List    ${levels}    ${s.level}
    END

    # No de-escalation during approach
    ${prev}=    Set Variable    ${0}
    FOR    ${lvl}    IN    @{levels}
        Should Be True    ${lvl} >= ${prev}
        ...    Warning de-escalated: ${prev} → ${lvl} during Vehicle A approach
        ${prev}=    Set Variable    ${lvl}
    END

    List Should Contain Value    ${levels}    ${WARN_CRITICAL}
    ...    CRITICAL level never reached during Vehicle A approach profile

TC-IS-003 Vehicle A Triggers FRONT_LEFT Sensor
    [Documentation]    The triggered_sensor field must identify FRONT_LEFT.
    [Tags]             intersection    vehicle-a    sensor-id

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${150}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${25}ms

    ${state}=    IS.Read Warning

    Should Be Equal As Integers    ${state.triggered_sensor}    ${SENSOR_FRONT_LEFT}
    ...    triggered_sensor=${state.triggered_sensor}, expected FRONT_LEFT=${SENSOR_FRONT_LEFT}

# ===========================================================================
# TC-IS-004: Timing — SR-CW-TIM-001 detection latency ≤ 50 ms
# ===========================================================================
TC-IS-004 Detection Latency Within 50 ms Budget
    [Documentation]    Sensor-read → detection decision must be ≤ 50 ms.
    ...                Verified across 50 consecutive trigger events.
    ...                Requirement: SR-CW-TIM-001 (AC-HIL-CW-003)
    [Tags]             timing    SR-CW-TIM-001    AC-HIL-CW-003

    ${max_lat}=    Set Variable    ${0}
    FOR    ${i}    IN RANGE    50
        IS.Clear All Radar
        Sleep    ${5}ms
        IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${180}
        ...               rel_vel_cms=${-100}    valid=${1}
        Sleep    ${25}ms
        ${state}=    IS.Read Warning
        IF    ${state.detection_lat_ms} > ${max_lat}
            ${max_lat}=    Set Variable    ${state.detection_lat_ms}
        END
    END

    Log    Max detection latency over 50 samples: ${max_lat} ms (budget: ${DETECTION_LATENCY_MAX} ms)
    Should Be True    ${max_lat} <= ${DETECTION_LATENCY_MAX}
    ...    Max detection latency ${max_lat} ms > ${DETECTION_LATENCY_MAX} ms (SR-CW-TIM-001)

# ===========================================================================
# TC-IS-005: Timing — SR-CW-TIM-002 warning GPIO latency ≤ 100 ms
# ===========================================================================
TC-IS-005 Warning Output Latency Within 100 ms Budget
    [Documentation]    Detection → warning GPIO assert must be ≤ 100 ms.
    ...                Verified across 50 consecutive trigger events.
    ...                Requirement: SR-CW-TIM-002 (AC-HIL-CW-003)
    [Tags]             timing    SR-CW-TIM-002    AC-HIL-CW-003

    ${max_lat}=    Set Variable    ${0}
    FOR    ${i}    IN RANGE    50
        IS.Clear All Radar
        Sleep    ${5}ms
        IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${150}
        ...               rel_vel_cms=${-100}    valid=${1}
        Sleep    ${30}ms
        ${state}=    IS.Read Warning
        IF    ${state.warning_lat_ms} > ${max_lat}
            ${max_lat}=    Set Variable    ${state.warning_lat_ms}
        END
    END

    Log    Max warning latency over 50 samples: ${max_lat} ms (budget: ${WARNING_LATENCY_MAX} ms)
    Should Be True    ${max_lat} <= ${WARNING_LATENCY_MAX}
    ...    Max warning latency ${max_lat} ms > ${WARNING_LATENCY_MAX} ms (SR-CW-TIM-002)

# ===========================================================================
# TC-IS-006: Timing — SR-CW-TIM-003 sensor poll period 10 ms ± 1 ms
# ===========================================================================
TC-IS-006 Sensor Poll Period Jitter Within 1 ms Under Load
    [Documentation]    Radar sensor polled at 10 ms ± 1 ms under multi-sensor load.
    ...                Requirement: SR-CW-TIM-003 (AC-HIL-CW-003)
    [Tags]             timing    SR-CW-TIM-003    AC-HIL-CW-003

    # Activate all 4 sensors simultaneously — worst-case polling load
    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}   distance_cm=${500}    rel_vel_cms=${-100}    valid=${1}
    IS.Write Radar    sensor_id=${SENSOR_FRONT_RIGHT}  distance_cm=${600}    rel_vel_cms=${-120}    valid=${1}
    IS.Write Radar    sensor_id=${SENSOR_REAR_LEFT}    distance_cm=${700}    rel_vel_cms=${-80}     valid=${1}
    IS.Write Radar    sensor_id=${SENSOR_REAR_RIGHT}   distance_cm=${800}    rel_vel_cms=${-60}     valid=${1}

    ${min_ms}    ${max_ms}=    HIL.Measure Poll Jitter    samples=50
    Log    Poll jitter: min=${min_ms} ms max=${max_ms} ms (nominal=10 ±1 ms)

    Should Be True    ${max_ms} <= ${POLL_PERIOD_MS} + ${POLL_JITTER_MS}
    ...    Poll period ${max_ms} ms exceeds 11 ms under 4-sensor load (SR-CW-TIM-003)
    Should Be True    ${min_ms} >= ${POLL_PERIOD_MS} - ${POLL_JITTER_MS}
    ...    Poll period ${min_ms} ms below 9 ms under 4-sensor load (SR-CW-TIM-003)

# ===========================================================================
# TC-IS-007: Vehicle A high-speed — CRITICAL via TTC at 4-way crossing
# ===========================================================================
TC-IS-007 Vehicle A High Speed CRITICAL Via TTC
    [Documentation]    Vehicle A at 3 m/s: TTC < 1500 ms at 300 cm → CRITICAL
    ...                before physical distance reaches CW_CRITICAL_DISTANCE_CM.
    [Tags]             intersection    vehicle-a    high-speed    ttc

    ${profile}=    Create List    900    700    500    300    200    100
    ${states}=    IS.Approach Profile
    ...    sensor_id=${SENSOR_FRONT_LEFT}    profile_cm=${profile}
    ...    vel_cms=-300    step_ms=${15}

    # At step 3 (300 cm, vel=300 cm/s) TTC = 1000 ms → must be CRITICAL
    ${step3}=    Get From List    ${states}    3
    Should Be Equal As Integers    ${step3.level}    ${WARN_CRITICAL}
    ...    Expected CRITICAL at 300 cm (TTC=1000 ms, vel=3 m/s), got ${step3.level_name()}

    ${final}=    Get From List    ${states}    -1
    Should Be Equal As Integers    ${final.level}    ${WARN_CRITICAL}
    ...    Final level should be CRITICAL; got ${final.level_name()}

# ===========================================================================
# TC-IS-008: Multi-vector threat — lower TTC dominates
# ===========================================================================
TC-IS-008 Multi-Vector Threat Selects Lower TTC Sensor
    [Documentation]    Two vehicles enter intersection simultaneously.
    ...                System must select FRONT_RIGHT (TTC=1000 ms) over
    ...                FRONT_LEFT (TTC=1500 ms) as the primary threat.
    [Tags]             intersection    multi-vehicle    ttc-selection

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}   distance_cm=${150}    rel_vel_cms=${-100}    valid=${1}
    IS.Write Radar    sensor_id=${SENSOR_FRONT_RIGHT}  distance_cm=${300}    rel_vel_cms=${-300}    valid=${1}
    Sleep    ${30}ms

    ${state}=    IS.Read Warning

    Should Be Equal As Integers    ${state.level}    ${WARN_CRITICAL}
    ...    Expected CRITICAL for simultaneous approach, got ${state.level_name()}

    Should Be Equal As Integers    ${state.triggered_sensor}    ${SENSOR_FRONT_RIGHT}
    ...    Triggered sensor should be FRONT_RIGHT (lower TTC), got ${state.triggered_sensor}

    Should Be True    ${state.ttc_ms} <= 1100
    ...    Reported TTC ${state.ttc_ms} ms should reflect FRONT_RIGHT (TTC≈1000 ms)

# ===========================================================================
# TC-IS-009: False positive — stationary object must not trigger CRITICAL
# ===========================================================================
TC-IS-009 Stationary Object Does Not Trigger CRITICAL Warning
    [Documentation]    A stationary object (zero velocity) at 200 cm must not
    ...                produce a CRITICAL warning.  Prevents spurious alerts
    ...                at stop signs and traffic lights.
    [Tags]             intersection    false-positive    stationary

    FOR    ${i}    IN RANGE    20
        IS.Write Radar
        ...    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${200}
        ...    rel_vel_cms=${0}    valid=${1}
        Sleep    ${POLL_PERIOD_MS}ms
    END

    ${state}=    IS.Read Warning
    Should Not Be Equal As Integers    ${state.level}    ${WARN_CRITICAL}
    ...    CRITICAL issued for stationary object at 200 cm — false positive

# ===========================================================================
# TC-IS-010: Receding vehicle — no warning issued
# ===========================================================================
TC-IS-010 Receding Vehicle Produces No Warning
    [Documentation]    Vehicle moving away (positive relative velocity) must not
    ...                trigger any warning level at any distance.
    [Tags]             intersection    false-positive    receding

    IS.Write Radar
    ...    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${300}
    ...    rel_vel_cms=${200}    valid=${1}
    Sleep    ${25}ms

    ${state}=    IS.Read Warning
    Should Be Equal As Integers    ${state.level}    ${WARN_NONE}
    ...    Warning=${state.level_name()} for receding vehicle (vel=+200 cm/s); expected NONE

# ===========================================================================
# TC-IS-011: Fault injection — sensor timeout → fail-safe NONE (AC-HIL-CW-002)
# ===========================================================================
TC-IS-011 Sensor Timeout Clears Warning To NONE Fail-Safe
    [Documentation]    When the radar sensor times out, the firmware must clear
    ...                the active warning to NONE (fail-safe: no false alarms
    ...                from stale data).  Fault flag must be set.
    ...                Requirement: AC-HIL-CW-002
    [Tags]             fault-injection    sensor-timeout    fail-safe    AC-HIL-CW-002

    # Establish advisory
    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${800}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${20}ms

    ${pre}=    IS.Read Warning
    Should Be True    ${pre.level} >= ${WARN_ADVISORY}
    ...    Pre-fault advisory not established (dist=800 cm, vel=-100 cm/s)

    # Inject timeout
    IS.Inject Fault    ${0x00000001}    # CW_FAULT_SENSOR_TIMEOUT
    Sleep    ${40}ms    # 3 poll cycles + margin

    ${fault_flags}=    IS.Read Fault Detected
    ${post}=    IS.Read Warning

    Should Be True    ${fault_flags} & 0x00000001
    ...    CW_FAULT_SENSOR_TIMEOUT flag NOT set in g_cw_fault_detected_flags
    Should Be Equal As Integers    ${post.level}    ${WARN_NONE}
    ...    Warning=${post.level_name()} after timeout; expected NONE (fail-safe)

TC-IS-012 Sensor Timeout Recovery Resumes Warning
    [Documentation]    After sensor timeout clears, warning must resume when
    ...                fresh radar data is available (AC-HIL-CW-002).
    [Tags]             fault-injection    sensor-timeout    recovery    AC-HIL-CW-002

    IS.Inject Fault    ${0x00000001}
    Sleep    ${50}ms
    IS.Clear Fault

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${400}
    ...               rel_vel_cms=${-150}    valid=${1}
    Sleep    ${25}ms

    ${state}=    IS.Read Warning
    Should Be True    ${state.level} > ${WARN_NONE}
    ...    Warning did not resume after sensor timeout recovery

# ===========================================================================
# TC-IS-013: Fault injection — stuck sensor must not escalate to CRITICAL
# ===========================================================================
TC-IS-013 Stuck Sensor Does Not Trigger CRITICAL
    [Documentation]    If radar output repeats the same distance for > 20 cycles,
    ...                firmware must detect the frozen signal.  CRITICAL must NOT
    ...                be issued from stale (stuck) data (AC-HIL-CW-002).
    [Tags]             fault-injection    sensor-stuck    AC-HIL-CW-002

    IS.Inject Fault    ${0x00000002}    # CW_FAULT_SENSOR_STUCK

    FOR    ${i}    IN RANGE    20
        IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${500}
        ...               rel_vel_cms=${-100}    valid=${1}
        Sleep    ${POLL_PERIOD_MS}ms
    END

    ${state}=    IS.Read Warning
    Should Not Be Equal As Integers    ${state.level}    ${WARN_CRITICAL}
    ...    CRITICAL issued from frozen sensor data — stuck-sensor fault not suppressed

    IS.Clear Fault

# ===========================================================================
# TC-IS-014: Fault injection — CAN error must not suppress CRITICAL warning
# ===========================================================================
TC-IS-014 CAN Bus Error Does Not Suppress Active CRITICAL Warning
    [Documentation]    A CAN bus error frame must not silence the collision warning
    ...                GPIO output.  Safety outputs are independent of CAN health.
    ...                Requirement: AC-HIL-CW-002
    [Tags]             fault-injection    can-bus    safety-independence    AC-HIL-CW-002

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${150}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${20}ms

    ${pre}=    IS.Read Warning
    Should Be Equal As Integers    ${pre.level}    ${WARN_CRITICAL}
    ...    CRITICAL not established before CAN fault (dist=150 cm, vel=-100 cm/s)

    ${prior_errors}=    IS.Read Can Error Count

    IS.Inject Fault    ${0x00000004}    # CW_FAULT_CAN_BUS_ERROR
    Sleep    ${50}ms

    ${fault_flags}=    IS.Read Fault Detected
    ${post_errors}=    IS.Read Can Error Count
    ${post}=    IS.Read Warning

    Should Be True    ${fault_flags} & 0x00000004
    ...    CW_FAULT_CAN_BUS_ERROR NOT detected by firmware
    Should Be True    ${post_errors} > ${prior_errors}
    ...    CAN error counter not incremented: before=${prior_errors} after=${post_errors}
    Should Be True    ${post.level} >= ${WARN_CAUTION}
    ...    Warning dropped to ${post.level_name()} during CAN fault; must remain ≥ CAUTION

    IS.Clear Fault

# ===========================================================================
# TC-IS-015: Fault injection — power glitch preserves warning state
# ===========================================================================
TC-IS-015 Power Glitch Does Not Lose Warning State
    [Documentation]    A brief power transient (< 50 µs in production, 5 ms HIL sim)
    ...                must not corrupt the warning state.  Firmware recovers and
    ...                re-asserts the same level within 50 ms.
    [Tags]             fault-injection    power-glitch    AC-HIL-CW-002

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${150}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${20}ms

    ${pre}=    IS.Read Warning
    ${pre_level}=    Set Variable    ${pre.level}

    IS.Inject Fault    ${0x00000008}    # CW_FAULT_POWER_GLITCH
    Sleep    ${5}ms
    IS.Clear Fault
    Sleep    ${50}ms

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${150}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${20}ms

    ${post}=    IS.Read Warning
    Should Be Equal As Integers    ${post.level}    ${pre_level}
    ...    Warning level changed from ${pre_level} to ${post.level} after power glitch

# ===========================================================================
# TC-IS-016: Blind corner — REAR_LEFT approach triggers warning
# ===========================================================================
TC-IS-016 Blind Corner REAR_LEFT Approach Triggers Warning
    [Documentation]    Vehicle A approaching blind corner from rear-left.
    ...                REAR_LEFT sensor must detect and warn.
    [Tags]             intersection    blind-corner    rear-sensor

    ${profile}=    Create List    600    450    350    250    150
    ${states}=    IS.Approach Profile
    ...    sensor_id=${SENSOR_REAR_LEFT}    profile_cm=${profile}
    ...    vel_cms=-200    step_ms=${15}

    ${final}=    Get From List    ${states}    -1

    Should Be True    ${final.level} >= ${WARN_CAUTION}
    ...    Expected CAUTION or CRITICAL for blind corner at 150 cm, got ${final.level_name()}

    Should Be Equal As Integers    ${final.triggered_sensor}    ${SENSOR_REAR_LEFT}
    ...    triggered_sensor=${final.triggered_sensor}, expected REAR_LEFT=${SENSOR_REAR_LEFT}

# ===========================================================================
# TC-IS-017: Warning hysteresis — no oscillation at thresholds
# ===========================================================================
TC-IS-017 Warning De-Escalates Smoothly During Vehicle Retreat
    [Documentation]    When vehicle A retreats from 200 cm to 800 cm, warning
    ...                must de-escalate without oscillating.  Level must never
    ...                re-escalate during a retreat sequence.
    [Tags]             intersection    hysteresis    retreat

    IS.Write Radar    sensor_id=${SENSOR_FRONT_LEFT}    distance_cm=${200}
    ...               rel_vel_cms=${-100}    valid=${1}
    Sleep    ${20}ms

    ${initial}=    IS.Read Warning
    Should Be Equal As Integers    ${initial.level}    ${WARN_CRITICAL}
    ...    CRITICAL not established at 200 cm before retreat test

    ${retreat}=    Create List    200    250    350    450    600    800
    ${states}=    IS.Approach Profile
    ...    sensor_id=${SENSOR_FRONT_LEFT}    profile_cm=${retreat}
    ...    vel_cms=${100}    step_ms=${15}

    ${prev}=    Set Variable    ${WARN_CRITICAL}
    FOR    ${s}    IN    @{states}
        Should Be True    ${s.level} <= ${prev}
        ...    Warning escalated during retreat: ${prev} → ${s.level}
        ${prev}=    Set Variable    ${s.level}
    END

    ${final}=    Get From List    ${states}    -1
    Should Be True    ${final.level} <= ${WARN_ADVISORY}
    ...    Warning ${final.level_name()} still active at 800 cm retreat; expected ≤ ADVISORY

# ===========================================================================
# TC-IS-018: Coverage gate — branch coverage ≥ 90 % (AC-HIL-CW-001)
# Must run last — counts all branches exercised by preceding test cases.
# ===========================================================================
TC-IS-018 Branch Coverage Meets 90 Percent Target
    [Documentation]    Read on-target g_cw_branch_covered / g_cw_branch_total
    ...                via GDB.  Coverage must be ≥ 90 % (SR-COV-001).
    ...                Requirement: AC-HIL-CW-001
    [Tags]             coverage    quality-gate    AC-HIL-CW-001
    [Setup]            No Operation    # no stub reset — preserve coverage counters

    ${covered}    ${total}=    HIL.Read Branch Coverage Counters
    ...    covered_addr=0x20002000    total_addr=0x20002004

    IF    ${total} == 0
        Log    Coverage counters not instrumented — gate skipped (non-coverage build)
        Skip
    END

    ${pct}=    Evaluate    (${covered} * 100) // ${total}
    Log    Branch coverage: ${covered}/${total} = ${pct}% (target: ${COVERAGE_TARGET_PCT}%)

    Should Be True    ${pct} >= ${COVERAGE_TARGET_PCT}
    ...    Branch coverage ${pct}% (${covered}/${total}) < ${COVERAGE_TARGET_PCT}% (SR-COV-001)

*** Keywords ***

Intersection Suite Setup
    [Documentation]    Connect to OpenOCD; open UART semihosting channel.
    HIL.Connect OpenOCD    host=${OPENOCD_HOST}    port=${OPENOCD_PORT}
    Run Keyword And Ignore Error    HIL.Connect UART    port=${SERIAL_PORT}
    IS.Connect    host=${OPENOCD_HOST}    port=${OPENOCD_PORT}
    Log    Intersection HIL suite setup complete

Intersection Suite Teardown
    [Documentation]    Clear faults and disconnect all interfaces.
    Run Keyword And Ignore Error    IS.Clear Fault
    Run Keyword And Ignore Error    IS.Clear All Radar
    Run Keyword And Ignore Error    HIL.Disconnect All
    Log    Intersection HIL suite teardown complete

Reset Radar Stubs And Faults
    [Documentation]    Clear all radar stubs and fault flags; allow 30 ms settle.
    IS.Clear All Radar
    IS.Clear Fault
    Sleep    ${SETTLE_MS}ms
