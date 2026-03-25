# ==============================================================================
# ARM GCC Toolchain File — STM32L476RG (Cortex-M4 with FPU)
# ==============================================================================
# Usage:
#   cmake -S firmware -B firmware/build-arm \
#         -DCMAKE_TOOLCHAIN_FILE=../toolchain-arm-gcc.cmake \
#         -DBUILD_FIRMWARE=ON \
#         -DBUILD_TESTS=OFF \
#         -DCMAKE_BUILD_TYPE=Release
#
# Requires arm-none-eabi-gcc 12.x on PATH, or set ARM_GCC_PATH env var:
#   export ARM_GCC_PATH=/opt/arm-gcc-12
# ==============================================================================

cmake_minimum_required(VERSION 3.26)

# ---------------------------------------------------------------------------
# Cross-compilation system identification
# ---------------------------------------------------------------------------
set(CMAKE_SYSTEM_NAME  Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# ---------------------------------------------------------------------------
# Toolchain discovery — respects ARM_GCC_PATH env var for CI / Docker
# ---------------------------------------------------------------------------
if(DEFINED ENV{ARM_GCC_PATH})
    set(_ARM_GCC_PREFIX "$ENV{ARM_GCC_PATH}/bin/arm-none-eabi-")
else()
    set(_ARM_GCC_PREFIX "arm-none-eabi-")
endif()

set(CMAKE_C_COMPILER    "${_ARM_GCC_PREFIX}gcc"     CACHE FILEPATH "C compiler")
set(CMAKE_CXX_COMPILER  "${_ARM_GCC_PREFIX}g++"     CACHE FILEPATH "C++ compiler")
set(CMAKE_ASM_COMPILER  "${_ARM_GCC_PREFIX}gcc"     CACHE FILEPATH "ASM compiler")
set(CMAKE_OBJCOPY       "${_ARM_GCC_PREFIX}objcopy"  CACHE FILEPATH "objcopy")
set(CMAKE_OBJDUMP       "${_ARM_GCC_PREFIX}objdump"  CACHE FILEPATH "objdump")
set(CMAKE_SIZE          "${_ARM_GCC_PREFIX}size"     CACHE FILEPATH "size")
set(CMAKE_AR            "${_ARM_GCC_PREFIX}ar"       CACHE FILEPATH "ar")
set(CMAKE_RANLIB        "${_ARM_GCC_PREFIX}ranlib"   CACHE FILEPATH "ranlib")

# ---------------------------------------------------------------------------
# MCU-specific flags for STM32L476RG
#   -mcpu=cortex-m4        Cortex-M4 instruction set
#   -mthumb                Thumb-2 encoding (required for Cortex-M)
#   -mfpu=fpv4-sp-d16      Single-precision FPU (FPv4)
#   -mfloat-abi=hard       Use FPU registers for float args (ABI)
# ---------------------------------------------------------------------------
set(_MCU_FLAGS
    -mcpu=cortex-m4
    -mthumb
    -mfpu=fpv4-sp-d16
    -mfloat-abi=hard
)
list(JOIN _MCU_FLAGS " " _MCU_FLAGS_STR)

# ---------------------------------------------------------------------------
# Common C compiler flags
# ---------------------------------------------------------------------------
set(CMAKE_C_FLAGS_INIT
    "${_MCU_FLAGS_STR}"
    " -ffunction-sections"
    " -fdata-sections"
    " -fno-common"
    " -fstack-usage"             # emit .su stack usage files per translation unit
    " -Wall"
    " -Wextra"
    " -Wshadow"
    " -Wdouble-promotion"
    " -Werror"
    " -DSTM32L476xx"
    " -DUSE_HAL_DRIVER"
)
# Flatten to a single string (CMake stores C_FLAGS_INIT as a string)
string(REPLACE ";" "" CMAKE_C_FLAGS_INIT "${CMAKE_C_FLAGS_INIT}")

set(CMAKE_ASM_FLAGS_INIT "${_MCU_FLAGS_STR} -x assembler-with-cpp")

# Build-type flags
set(CMAKE_C_FLAGS_DEBUG          "-Og -g3 -DDEBUG"          CACHE STRING "Debug flags")
set(CMAKE_C_FLAGS_RELEASE        "-O2 -DNDEBUG"             CACHE STRING "Release flags")
set(CMAKE_C_FLAGS_RELWITHDEBINFO "-O2 -g -DNDEBUG"          CACHE STRING "RelWithDebInfo flags")
set(CMAKE_C_FLAGS_MINSIZEREL     "-Os -DNDEBUG"             CACHE STRING "MinSizeRel flags")

# ---------------------------------------------------------------------------
# Linker flags
#   --specs=nano.specs    Link against newlib-nano (smaller libc)
#   --specs=nosys.specs   Stub out syscalls (no OS)
#   --gc-sections         Remove unused code/data sections
#   --print-memory-usage  Report flash/RAM usage at link time
# ---------------------------------------------------------------------------
set(CMAKE_EXE_LINKER_FLAGS_INIT
    "${_MCU_FLAGS_STR}"
    " -Wl,--gc-sections"
    " -Wl,--print-memory-usage"
    " --specs=nano.specs"
    " --specs=nosys.specs"
    " -lc -lm -lnosys"
)
string(REPLACE ";" "" CMAKE_EXE_LINKER_FLAGS_INIT "${CMAKE_EXE_LINKER_FLAGS_INIT}")

# ---------------------------------------------------------------------------
# Prevent CMake from trying to run a test executable on the host
# ---------------------------------------------------------------------------
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

# ---------------------------------------------------------------------------
# Search paths — look only in the embedded sysroot, never on the build host
# ---------------------------------------------------------------------------
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
