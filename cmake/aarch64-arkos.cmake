# Toolchain für Cross-Compile auf den M9 Pro (RK3326, Cortex-A35, Mali-G31).

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
if(DEFINED SDL2_INSTALL_DIR)
    list(APPEND CMAKE_FIND_ROOT_PATH ${SDL2_INSTALL_DIR})
endif()

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# CPU: Cortex-A35 (RK3326). -march vor -mcpu.
# -mno-outline-atomics ist KRITISCH: ohne das SIGILL beim ersten
# atomaren Zugriff (A35 hat kein LSE).
set(_WOTS2_CPU "-march=armv8-a+crc -mcpu=cortex-a35 -mtune=cortex-a35 -mno-outline-atomics")

# Cortex-A35: Software-Prefetching für Schleifen aktivieren.
# Der A35 hat nur einen Load/Store-Port – Prefetching versteckt Latenzen.
set(_WOTS2_OPT "-O3 -funroll-loops -fprefetch-loop-arrays -fno-math-errno -fno-trapping-math -fomit-frame-pointer -ffunction-sections -fdata-sections -fno-plt -fno-semantic-interposition -fno-strict-aliasing -fmerge-all-constants -fno-common -DNDEBUG -Wno-psabi")

# Kein -flto hier: LTO ist global aus (GCC-Bug 92872 mit ODR-Verstößen).
set(_WOTS2_LD "-Wl,--gc-sections -Wl,--as-needed -Wl,-O2 -Wl,--sort-common")

set(CMAKE_C_FLAGS_INIT   "${_WOTS2_CPU} ${_WOTS2_OPT}")
set(CMAKE_CXX_FLAGS_INIT "${_WOTS2_CPU} ${_WOTS2_OPT}")

set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_WOTS2_LD}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_WOTS2_LD}")

# ── Runtime-Robustheit (ArkOS / GLIBC 2.31) ──────────────────────────
# NUR C++- und GCC-Runtime statisch einbinden.
# libc.so.6 bleibt dynamisch → GLIBC 2.31 Kompatibilität bleibt unangetastet.
set(CMAKE_EXE_LINKER_FLAGS_INIT
    "${CMAKE_EXE_LINKER_FLAGS_INIT} -static-libstdc++ -static-libgcc")
