cmake_minimum_required(VERSION 3.20)

# ============================================================================
# Fall Detection Firmware — CMake Build System
# Target: ARM Cortex-M4 (adapt toolchain file for your MCU)
# ============================================================================
project(fall_detection_firmware C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ----------------------------------------------------------------------------
# Options
# ----------------------------------------------------------------------------
option(BUILD_TESTS    "Build unit tests (host)"         ON)
option(BUILD_FIRMWARE "Build firmware (cross-compile)"  OFF)
option(OTA_USE_MBEDTLS "Enable mbedTLS OTA verification" OFF)

# ----------------------------------------------------------------------------
# Version (injected as preprocessor defines)
# ----------------------------------------------------------------------------
set(FW_VERSION_MAJOR 1)
set(FW_VERSION_MINOR 0)
set(FW_VERSION_PATCH 0)

# ----------------------------------------------------------------------------
# Compiler flags (common)
# ----------------------------------------------------------------------------
set(COMMON_FLAGS
    -Wall
    -Wextra
    -Wpedantic
    -Werror
    -Wshadow
    -Wdouble-promotion
    -ffunction-sections
    -fdata-sections
)

# ----------------------------------------------------------------------------
# Fall detection library (platform-independent algorithm)
# ----------------------------------------------------------------------------
add_library(fall_detection STATIC
    src/fall_detection.c
    src/ota_update.c
    src/watchdog.c
)

target_include_directories(fall_detection PUBLIC src/)

target_compile_definitions(fall_detection PRIVATE
    FW_VERSION_MAJOR=${FW_VERSION_MAJOR}
    FW_VERSION_MINOR=${FW_VERSION_MINOR}
    FW_VERSION_PATCH=${FW_VERSION_PATCH}
    $<$<BOOL:${OTA_USE_MBEDTLS}>:OTA_USE_MBEDTLS>
)

target_compile_options(fall_detection PRIVATE ${COMMON_FLAGS})

# mbedTLS integration (optional)
if(OTA_USE_MBEDTLS)
    find_package(MbedTLS REQUIRED)
    target_link_libraries(fall_detection PRIVATE MbedTLS::mbedtls)
endif()

# ----------------------------------------------------------------------------
# Hello-world blinky target
# Validates fall_detection library links correctly on the host (or in QEMU).
# CI runs this binary; exit code 0 means the library compiles and links clean.
# ----------------------------------------------------------------------------
add_executable(blinky_hello
    src/blinky_hello.c
)
target_link_libraries(blinky_hello PRIVATE fall_detection m)
target_compile_options(blinky_hello PRIVATE -Wall -Wextra)
target_compile_definitions(blinky_hello PRIVATE
    FW_VERSION_MAJOR=${FW_VERSION_MAJOR}
    FW_VERSION_MINOR=${FW_VERSION_MINOR}
    FW_VERSION_PATCH=${FW_VERSION_PATCH}
)

# ----------------------------------------------------------------------------
# Host-native test build
# ----------------------------------------------------------------------------
if(BUILD_TESTS)
    enable_testing()

    # Fetch Unity if not present
    include(FetchContent)
    FetchContent_Declare(
        unity
        GIT_REPOSITORY https://github.com/ThrowTheSwitch/Unity.git
        GIT_TAG        v2.6.0
    )
    FetchContent_MakeAvailable(unity)

    # BSP stubs for host testing
    add_library(bsp_stub STATIC tests/bsp_stub.c)
    target_include_directories(bsp_stub PUBLIC src/)

    # Test executable
    add_executable(test_fall_detection
        tests/test_fall_detection.c
    )

    target_link_libraries(test_fall_detection
        fall_detection
        bsp_stub
        unity
        m        # libm for sqrtf / sinf
    )

    target_compile_options(test_fall_detection PRIVATE
        -Wall -Wextra -g -O0
        --coverage           # gcov coverage
        -fprofile-arcs
        -ftest-coverage
    )

    target_link_options(test_fall_detection PRIVATE --coverage)

    add_test(NAME fall_detection_unit_tests
             COMMAND test_fall_detection)

    # Coverage report target
    find_program(GCOVR gcovr)
    if(GCOVR)
        add_custom_target(coverage
            COMMAND ${GCOVR}
                --root ${CMAKE_SOURCE_DIR}
                --filter ${CMAKE_SOURCE_DIR}/src/
                --html --html-details
                -o ${CMAKE_BINARY_DIR}/coverage.html
                --print-summary
            DEPENDS test_fall_detection
            COMMENT "Generating coverage report"
        )
    endif()
endif()

# ----------------------------------------------------------------------------
# Firmware cross-compile target (enable with -DBUILD_FIRMWARE=ON)
# ----------------------------------------------------------------------------
if(BUILD_FIRMWARE)
    if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
        message(FATAL_ERROR
            "Specify toolchain: -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake")
    endif()

    add_executable(firmware.elf
        src/main.c
    )

    target_link_libraries(firmware.elf
        fall_detection
        # Add your BSP and HAL libraries here:
        # hal_stm32l4
        # freertos_kernel
    )

    target_link_options(firmware.elf PRIVATE
        -Wl,--gc-sections
        -Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map
        -T${CMAKE_SOURCE_DIR}/linker/stm32l476rg.ld
    )

    # Generate binary and hex artifacts
    add_custom_command(TARGET firmware.elf POST_BUILD
        COMMAND ${CMAKE_OBJCOPY} -O binary firmware.elf firmware.bin
        COMMAND ${CMAKE_OBJCOPY} -O ihex   firmware.elf firmware.hex
        COMMAND ${CMAKE_SIZE}    firmware.elf
        COMMENT "Generating firmware.bin and firmware.hex"
    )
endif()

# ----------------------------------------------------------------------------
# Install targets
# ----------------------------------------------------------------------------
install(FILES
    src/fall_detection.h
    src/ota_update.h
    src/watchdog.h
    DESTINATION include/fall_detection
)
