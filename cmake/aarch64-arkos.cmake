# cmake/aarch64-arkos.cmake
#
# Cross-Toolchain für M9 Pro / R36S / RK3326 (Cortex-A35, Mali-G31 MP2).
# Ziel: ArkOS4Clone mit glibc 2.31 (Ubuntu 20.04 focal, arm64).
#
# Kritische Flags:
#   -mno-outline-atomics     Cortex-A35 hat keine LSE-Atomics; ohne dieses
#                            Flag ruft GCC __aarch64_ldadd4_acq_rel auf,
#                            was zum SIGILL beim ersten atomaren Zugriff
#                            führt.
#   -static-libstdc++        NUR die C++/GCC-Runtime statisch, libc.so.6
#   -static-libgcc           bleibt dynamisch (glibc-2.31-Kompatibilität).
#                            KEIN -static, KEIN -static-libc.
#   -fno-unwind-tables       keine Exceptions im Spiel; spart Speicher
#   -fno-async-unwind-tables
#   -fno-stack-protector     kein Canary pro Funktion
#
# Bewusst NICHT gesetzt:
#   -flto                    bricht ImGui
#   -static                  bricht glibc-2.31-Kompatibilität
#   -mfix-cortex-a53-*       Cortex-A53-Errata; A35 ist nicht betroffen

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_AR           aarch64-linux-gnu-ar)
set(CMAKE_RANLIB       aarch64-linux-gnu-ranlib)
set(CMAKE_STRIP        aarch64-linux-gnu-strip)
set(CMAKE_OBJCOPY      aarch64-linux-gnu-objcopy)
set(CMAKE_OBJDUMP      aarch64-linux-gnu-objdump)

set(_WOTS2_CPU "-march=armv8-a+crc -mcpu=cortex-a35 -mtune=cortex-a35 -mno-outline-atomics")

set(_WOTS2_OPT "-O3 -funroll-loops -fprefetch-loop-arrays \
                -fno-math-errno -fno-trapping-math -fomit-frame-pointer \
                -ffunction-sections -fdata-sections \
                -fno-plt -fno-semantic-interposition \
                -fno-strict-aliasing -fmerge-all-constants -fno-common \
                -fno-unwind-tables -fno-asynchronous-unwind-tables \
                -fno-stack-protector \
                -DNDEBUG -Wno-psabi -Wno-unused-result")

set(_WOTS2_LD "-Wl,--gc-sections -Wl,--as-needed -Wl,-O2 -Wl,--sort-common")

set(CMAKE_C_FLAGS_INIT   "${_WOTS2_CPU} ${_WOTS2_OPT}")
set(CMAKE_CXX_FLAGS_INIT "${_WOTS2_CPU} ${_WOTS2_OPT}")
set(CMAKE_EXE_LINKER_FLAGS_INIT "${_WOTS2_LD}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_WOTS2_LD}")

# NUR die C++- und GCC-Runtime statisch; libc.so.6 dynamisch lassen.
set(CMAKE_EXE_LINKER_FLAGS_INIT
    "${CMAKE_EXE_LINKER_FLAGS_INIT} -static-libstdc++ -static-libgcc")
set(CMAKE_SHARED_LINKER_FLAGS_INIT
    "${CMAKE_SHARED_LINKER_FLAGS_INIT} -static-libstdc++ -static-libgcc")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
