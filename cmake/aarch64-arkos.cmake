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

# ── CPU: Cortex-A35 (RK3326) ────────────────────────────────────────────
# Quellen:
#   GCC AArch64 Options
#     https://gcc.gnu.org/onlinedocs/gcc/AArch64-Options.html
#   ARM Cortex-A35 TRM: ARMv8.0-A, kein LSE, CRC-Extension vorhanden
#
# -march MUSS vor -mcpu stehen: -mcpu erweitert die -march-Auswahl um
# Cortex-A35-spezifische Details. Umgekehrte Reihenfolge führt zu
# Warnungen oder falscher Codegen.
#
# -mno-outline-atomics ist KRITISCH: Der Cortex-A35 hat keine
# Large-System-Extensions. Ohne dieses Flag emittiert GCC Aufrufe an
# __aarch64_ldadd4_acq_rel, eine libgcc-Funktion mit LSE-Instruktionen
# → SIGILL beim ersten atomaren Zugriff.
#
# WICHTIG: Alle Flags als EIN String mit Leerzeichen, NICHT als CMake-
# Liste. CMake würde eine Liste mit Semikolons an GCC übergeben, was
# GCC als ein einziges Argument interpretiert ("no input files").
set(_WOTS2_CPU "-march=armv8-a+crc -mcpu=cortex-a35 -mtune=cortex-a35 -mno-outline-atomics")

# ── Optimierung ─────────────────────────────────────────────────────────
set(_WOTS2_OPT "-O3 -funroll-loops -fno-math-errno -fno-trapping-math -fomit-frame-pointer -ffunction-sections -fdata-sections -fno-plt -fno-semantic-interposition -fno-strict-aliasing -fmerge-all-constants -fno-common -DNDEBUG -Wno-psabi")

# ── Linker ──────────────────────────────────────────────────────────────
# -flto hier NICHT setzen: CMake aktiviert es für alle Targets über
# CMAKE_INTERPROCEDURAL_OPTIMIZATION (in CMakeLists.txt). Das erlaubt
# imgui, LTO abzuschalten (nötig wegen static initializers).
set(_WOTS2_LD "-Wl,--gc-sections -Wl,--as-needed -Wl,-O2 -Wl,--sort-common")

set(CMAKE_C_FLAGS_INIT   "${_WOTS2_CPU} ${_WOTS2_OPT}")
set(CMAKE_CXX_FLAGS_INIT "${_WOTS2_CPU} ${_WOTS2_OPT}")

set(CMAKE_EXE_LINKER_FLAGS_INIT    "${_WOTS2_LD}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_WOTS2_LD}")
