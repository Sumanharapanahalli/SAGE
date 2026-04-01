# CMakeLists.txt — Wearable Fall Detection Firmware
# Target: nRF5340 Application Core (Cortex-M33) + nRF9160 modem
# SDK: nRF Connect SDK v2.6 (Zephyr RTOS)
# Toolchain: arm-zephyr-eabi (Zephyr SDK 0.16+)
#
# Build variants:
#   Production : cmake -B build -DBOARD=nrf5340dk_nrf5340_cpuapp
#   HIL test   : cmake -B build_hil -DBOARD=nrf5340dk_nrf5340_cpuapp \
#                       -DOVERLAY_CONFIG=overlay-hil.conf
#
# IEC 62304 traceability: SWD-BUILD-001

cmake_minimum_required(VERSION 3.20.0)

# ── nRF Connect SDK / Zephyr ─────────────────────────────────────────────────
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(wearable_fall_detection VERSION 1.0.0 LANGUAGES C)

# ── Compiler hardening (MISRA-C baseline flags) ───────────────────────────────
target_compile_options(app PRIVATE
    -Wall
    -Wextra
    -Werror
    -Wno-unused-parameter       # Zephyr macros use ARG_UNUSED — suppress
    -fstack-usage               # Generate .su files for stack analysis
    -fno-common                 # Each symbol defined once
    -ffunction-sections         # Dead-code elimination via linker
    -fdata-sections
    # MISRA-relevant
    -Wimplicit-function-declaration
    -Wstrict-prototypes
    -Wmissing-prototypes
    -Wshadow
    -Wundef
    -Wcast-align
    -Wconversion
    -Wsign-conversion
)

# ── Source files ──────────────────────────────────────────────────────────────
target_sources(app PRIVATE
    src/fall_detection.c
    src/gps_module.c
    src/lte_module.c
    src/battery_mgmt.c
    src/ble_gatt.c
    src/ota_update.c
    src/power_manager.c
    src/app_events.c
    src/main.c
)

# HIL interface only in test builds (guard enforced in C source too)
if(CONFIG_HIL_TEST_INTERFACE)
    target_sources(app PRIVATE src/hil_test_interface.c)
    message(STATUS "HIL test interface: ENABLED")
else()
    message(STATUS "HIL test interface: DISABLED (production build)")
endif()

# ── Include paths ─────────────────────────────────────────────────────────────
target_include_directories(app PRIVATE
    include
    src
)

# ── Version string baked into firmware ───────────────────────────────────────
target_compile_definitions(app PRIVATE
    CONFIG_APP_VERSION="${PROJECT_VERSION}"
)

# ── Static analysis integration (cppcheck, invoked via 'make analyze') ────────
find_program(CPPCHECK cppcheck)
if(CPPCHECK)
    add_custom_target(analyze
        COMMAND ${CPPCHECK}
            --enable=all
            --std=c11
            --suppress=missingIncludeSystem
            --suppress=unusedFunction
            --addon=misra
            --error-exitcode=1
            --xml
            --output-file=${CMAKE_BINARY_DIR}/cppcheck_report.xml
            ${CMAKE_SOURCE_DIR}/src
        COMMENT "Running cppcheck + MISRA analysis"
    )
endif()

# ── Binary size report (post-build) ──────────────────────────────────────────
add_custom_command(TARGET app POST_BUILD
    COMMAND ${CMAKE_SIZE} -A $<TARGET_FILE:app>
    COMMAND ${CMAKE_OBJDUMP} -h $<TARGET_FILE:app> >
            ${CMAKE_BINARY_DIR}/sections.txt
    COMMENT "Generating binary size report"
)

# ── Flash target via OpenOCD ──────────────────────────────────────────────────
find_program(OPENOCD openocd)
if(OPENOCD)
    add_custom_target(flash
        COMMAND ${OPENOCD}
            -f interface/jlink.cfg
            -f target/nrf5340.cfg
            -c "program $<TARGET_FILE:app> verify reset exit"
        DEPENDS app
        COMMENT "Flashing via OpenOCD/J-Link"
    )
    add_custom_target(flash_hil
        COMMAND ${OPENOCD}
            -f interface/jlink.cfg
            -f target/nrf5340.cfg
            -c "program ${CMAKE_BINARY_DIR}/zephyr/zephyr.hex verify reset exit"
        DEPENDS app
        COMMENT "Flashing HIL build via OpenOCD/J-Link"
    )
endif()

# ── GDB debug helper ──────────────────────────────────────────────────────────
find_program(GDB arm-zephyr-eabi-gdb
             HINTS $ENV{ZEPHYR_SDK_INSTALL_DIR}/arm-zephyr-eabi/bin)
if(GDB)
    add_custom_target(debug
        COMMAND ${GDB}
            -ex "target extended-remote localhost:3333"
            -ex "monitor reset halt"
            $<TARGET_FILE:app>
        DEPENDS app
        COMMENT "Attach GDB via OpenOCD (start openocd first)"
    )
endif()
