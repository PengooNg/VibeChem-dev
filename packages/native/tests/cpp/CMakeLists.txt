# SPDX-License-Identifier: GPL-3.0-or-later
# Catch2 unit tests for the C++ kernels (built only with -DVIBECHEM_BUILD_TESTS=ON).
include(FetchContent)
FetchContent_Declare(
  Catch2
  GIT_REPOSITORY https://github.com/catchorg/Catch2.git
  GIT_TAG        v3.16.1
  GIT_SHALLOW    TRUE)
FetchContent_MakeAvailable(Catch2)

add_executable(vibechem_native_tests test_row_mean.cpp)
target_link_libraries(vibechem_native_tests PRIVATE vibechem_kernels Catch2::Catch2WithMain)
target_compile_options(vibechem_native_tests PRIVATE ${VIBECHEM_WARNINGS})

include(Catch)
catch_discover_tests(vibechem_native_tests)
