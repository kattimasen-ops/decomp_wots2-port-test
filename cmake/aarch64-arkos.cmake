# Toolchain file for cross-compiling Way of the Samurai 2 to the M9 Pro
# (RK3326, Cortex-A35, Mali-G31) running ArkOS4Clone.

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

# Search paths for headers and libraries.
set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
if(DEFINED SDL2_INSTALL_DIR)
    list(APPEND CMAKE_FIND_ROOT_PATH ${SDL2_INSTALL_DIR})
endif()

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# ── Cortex-A35 specific optimization ─────────────────────────────────────
# Quellen:
#   GCC AArch64 Options:
#     https://gcc.gnu.org/onlinedocs/gcc/AArch64-Options.html
#   ARM Cortex-A35 TRM: ARMv8.0-A, kein LSE, CRC-Extension vorhanden
set(_WOTS2_CPU
    "-mcpu=cortex-a35"
    "-mtune=cortex-a35"
    "-mno-outline-atomics"     # KRITISCH: kein LSE auf A35 -> SIGILL ohne das
    "-march=armv8-a+crc"
)

set(_WOTS2_OPT
    "-O3"
    "-funroll-loops"
    "-fno-math-errno"
    "-fno-trapping-math"
    "-fomit-frame-pointer"
    "-ffunction-sections"
    "-fdata-sections"
    "-fno-plt"
    "-fno-semantic-interposition"
    "-fno-strict-aliasing"
    "-fmerge-all-constants"
    "-fno-common"
    "-DNDEBUG"
    "-Wno-psabi"
)

set(_WOTS2_LTO "-flto=auto")

set(_WOTS2_LD
    "-flto=auto"
    "-Wl,--gc-sections"
    "-Wl,--as-needed"
    "-Wl,-O2"
    "-Wl,--sort-common"
)

set(CMAKE_C_FLAGS_INIT   "${_WOTS2_CPU} ${_WOTS2_OPT} ${_WOTS2_LTO}")
set(CMAKE_CXX_FLAGS_INIT "${_WOTS2_CPU} ${_WOTS2_OPT} ${_WOTS2_LTO}")

set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_WOTS2_LD}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_WOTS2_LD}")
