cmake_minimum_required(VERSION 3.22)

# ---------------------------------------------------------------------------
# HIL Test Firmware — STM32WB55RGV6
# Toolchain: arm-none-eabi-gcc 12.x
# ---------------------------------------------------------------------------
set(CMAKE_TOOLCHAIN_FILE "${CMAKE_SOURCE_DIR}/cmake/arm-none-eabi.cmake")
project(sage_hil_tests C ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# MCU target flags
# ---------------------------------------------------------------------------
set(MCU_FLAGS
    -mcpu=cortex-m4
    -mthumb
    -mfpu=fpv4-sp-d16
    -mfloat-abi=hard
)

# ---------------------------------------------------------------------------
# Compiler flags — MISRA-C compatible, max warnings
# ---------------------------------------------------------------------------
set(C_WARNINGS
    -Wall
    -Wextra
    -Wpedantic
    -Wconversion
    -Wshadow
    -Wcast-qual
    -Wstrict-prototypes
    -Wmissing-prototypes
    -Werror
)

set(C_DEFINES
    -DSTM32WB55xx
    -DUSE_HAL_DRIVER
    -DHIL_BUILD=1
    -DDEBUG
)

# ---------------------------------------------------------------------------
# Include paths
# ---------------------------------------------------------------------------
set(HIL_INCLUDES
    include
    ../firmware/src
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Inc
    ${CMAKE_SOURCE_DIR}/Drivers/CMSIS/Device/ST/STM32WBxx/Include
    ${CMAKE_SOURCE_DIR}/Drivers/CMSIS/Include
    ${CMAKE_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/include
)

# ---------------------------------------------------------------------------
# HIL firmware sources
# ---------------------------------------------------------------------------
set(HIL_SOURCES
    src/hil_test_runner.c
    src/hil_sensor_tests.c
    src/hil_fault_injection.c
    src/hil_timing_tests.c
    src/hil_actuator_tests.c
    src/hil_comms_tests.c
    # HAL stubs (override production HAL for HIL context)
    stubs/fault_relay_hal.c
    stubs/hil_bsp.c
)

# STM32 HAL driver sources (subset needed for HIL)
file(GLOB HAL_SOURCES
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_cortex.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_gpio.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_spi.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_i2c.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_uart.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_tim.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_rcc.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_pwr.c
    ${CMAKE_SOURCE_DIR}/Drivers/STM32WBxx_HAL_Driver/Src/stm32wbxx_hal_dma.c
)

set(STARTUP_SOURCE
    ${CMAKE_SOURCE_DIR}/startup/startup_stm32wb55rgvx.s
)

# ---------------------------------------------------------------------------
# Linker script — HIL variant places .hil_result at 0x2000_0000
# ---------------------------------------------------------------------------
set(LINKER_SCRIPT "${CMAKE_SOURCE_DIR}/ldscripts/STM32WB55RGVX_hil.ld")

# ---------------------------------------------------------------------------
# HIL test firmware target
# ---------------------------------------------------------------------------
add_executable(sage_hil_tests.elf
    ${HIL_SOURCES}
    ${HAL_SOURCES}
    ${STARTUP_SOURCE}
)

target_include_directories(sage_hil_tests.elf PRIVATE ${HIL_INCLUDES})

target_compile_options(sage_hil_tests.elf PRIVATE
    ${MCU_FLAGS}
    ${C_WARNINGS}
    ${C_DEFINES}
    -ffunction-sections
    -fdata-sections
    -fno-common
    -fstack-usage           # generates .su files for stack analysis
    -g3
    -Og                     # debug-friendly optimization
)

target_link_options(sage_hil_tests.elf PRIVATE
    ${MCU_FLAGS}
    -T${LINKER_SCRIPT}
    -Wl,--gc-sections
    -Wl,--print-memory-usage
    -Wl,-Map=${CMAKE_BINARY_DIR}/sage_hil_tests.map
    --specs=nano.specs
    --specs=rdimon.specs    # semihosting (UART printf)
    -lrdimon
    -lc
    -lm
    -lnosys
)

# ---------------------------------------------------------------------------
# Post-build: generate binary + hex + size report
# ---------------------------------------------------------------------------
add_custom_command(TARGET sage_hil_tests.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary
        ${CMAKE_BINARY_DIR}/sage_hil_tests.elf
        ${CMAKE_BINARY_DIR}/sage_hil_tests.bin
    COMMAND ${CMAKE_OBJCOPY} -O ihex
        ${CMAKE_BINARY_DIR}/sage_hil_tests.elf
        ${CMAKE_BINARY_DIR}/sage_hil_tests.hex
    COMMAND ${CMAKE_SIZE} --format=berkeley
        ${CMAKE_BINARY_DIR}/sage_hil_tests.elf
    COMMENT "Generating HIL test binary artifacts"
)

# ---------------------------------------------------------------------------
# Flash target: OpenOCD
# ---------------------------------------------------------------------------
add_custom_target(flash
    COMMAND openocd
        -f interface/stlink.cfg
        -f target/stm32wbx.cfg
        -c "program ${CMAKE_BINARY_DIR}/sage_hil_tests.elf verify reset exit"
    DEPENDS sage_hil_tests.elf
    COMMENT "Flashing HIL firmware via OpenOCD + ST-Link"
)

# ---------------------------------------------------------------------------
# Coverage target: gcovr HTML report (requires -coverage build)
# ---------------------------------------------------------------------------
option(HIL_COVERAGE "Enable gcov coverage instrumentation" OFF)

if(HIL_COVERAGE)
    target_compile_options(sage_hil_tests.elf PRIVATE --coverage -fprofile-arcs -ftest-coverage)
    target_link_options(sage_hil_tests.elf PRIVATE --coverage)

    add_custom_target(coverage
        COMMAND gcovr
            --root ${CMAKE_SOURCE_DIR}/src
            --html --html-details
            -o ${CMAKE_BINARY_DIR}/coverage/index.html
            --print-summary
            --fail-under-branch ${HIL_COVERAGE_TARGET_PCT}
        DEPENDS sage_hil_tests.elf
        COMMENT "Generating HIL branch coverage report (target ≥ ${HIL_COVERAGE_TARGET_PCT}%)"
    )
endif()

# ---------------------------------------------------------------------------
# HIL_004: Sensor Data Validation — unit tests (Unity framework)
# ---------------------------------------------------------------------------
include(FetchContent)
FetchContent_Declare(
    unity
    GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
    GIT_TAG        v2.5.2
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(unity)

add_library(sensor_hal_lib STATIC
    sensor_hal.c
)
target_include_directories(sensor_hal_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(test_sensor_unit.elf
    test_sensor_unit.c
)
target_link_libraries(test_sensor_unit.elf
    PRIVATE sensor_hal_lib unity
)
target_include_directories(test_sensor_unit.elf PRIVATE ${HIL_INCLUDES})
target_compile_options(test_sensor_unit.elf PRIVATE
    ${MCU_FLAGS}
    ${C_WARNINGS}
    -DUNIT_TEST
    # Redirect peripheral base to simulated struct for host-side testing
    "-DSENSOR_PERIPH_BASE=((uint32_t)&g_sensor_regs_sim)"
    -Og -g3
)
target_link_options(test_sensor_unit.elf PRIVATE
    ${MCU_FLAGS}
    -Wl,--gc-sections
    --specs=nano.specs
    --specs=rdimon.specs
    -lrdimon -lc -lm -lnosys
)

# Post-build size report
add_custom_command(TARGET test_sensor_unit.elf POST_BUILD
    COMMAND ${CMAKE_SIZE} --format=berkeley $<TARGET_FILE:test_sensor_unit.elf>
    COMMENT "Sensor HAL unit test binary sizes"
)

# CTest: run unit tests under QEMU Cortex-M4 emulation
enable_testing()
add_test(
    NAME hil003_unit_sensor_hal
    COMMAND qemu-arm -cpu cortex-m4
            $<TARGET_FILE:test_sensor_unit.elf>
)
set_tests_properties(hil003_unit_sensor_hal PROPERTIES
    TIMEOUT              30
    PASS_REGULAR_EXPRESSION "OK"
    FAIL_REGULAR_EXPRESSION "FAIL"
    LABELS               "HIL_004;unit"
)

# CTest: Python HIL harness (requires live target + OpenOCD)
add_test(
    NAME hil003_pytest_harness
    COMMAND python3 -m pytest ${CMAKE_CURRENT_SOURCE_DIR}/hil_test_harness.py
            -v --timeout=60
)
set_tests_properties(hil003_pytest_harness PROPERTIES
    TIMEOUT   120
    LABELS    "HIL_004;integration;requires_hardware"
)

# CTest: Robot Framework specs (requires live target + OpenOCD)
add_test(
    NAME hil003_robot_specs
    COMMAND robot
            --outputdir ${CMAKE_BINARY_DIR}/robot_results
            --variable OPENOCD_HOST:127.0.0.1
            --variable OPENOCD_PORT:4444
            ${CMAKE_CURRENT_SOURCE_DIR}/hil_test_specs.robot
)
set_tests_properties(hil003_robot_specs PROPERTIES
    TIMEOUT   180
    LABELS    "HIL_004;integration;requires_hardware"
)
