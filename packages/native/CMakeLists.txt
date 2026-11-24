# SPDX-License-Identifier: GPL-3.0-or-later
# Build of the vibechem_native extension (scikit-build-core + nanobind).
# Layout follows wjakob/nanobind_example and the nanobind packaging guide (BSD-3-Clause).
cmake_minimum_required(VERSION 3.28...3.31)
project(vibechem_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(VIBECHEM_BUILD_TESTS "Build the Catch2 tests in tests/cpp" OFF)

# Warnings as errors for our own code (TECH_STACK.md §5)
if(MSVC)
  set(VIBECHEM_WARNINGS /W4 /WX /permissive-)
else()
  set(VIBECHEM_WARNINGS -Wall -Wextra -Wpedantic -Werror)
endif()

# Kernels: plain C++ library, shared by the extension and the Catch2 tests
add_library(vibechem_kernels STATIC src/row_mean.cpp)
target_include_directories(vibechem_kernels PUBLIC include)
target_compile_options(vibechem_kernels PRIVATE ${VIBECHEM_WARNINGS})
set_target_properties(vibechem_kernels PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(SKBUILD)
  find_package(Python 3.12
    REQUIRED COMPONENTS Interpreter Development.Module
    OPTIONAL_COMPONENTS Development.SABIModule)
  find_package(nanobind CONFIG REQUIRED)

  nanobind_add_module(_core STABLE_ABI NB_STATIC NB_SUPPRESS_WARNINGS bindings/module.cpp)
  target_link_libraries(_core PRIVATE vibechem_kernels)
  target_compile_options(_core PRIVATE ${VIBECHEM_WARNINGS})
  install(TARGETS _core LIBRARY DESTINATION vibechem_native)
endif()

if(VIBECHEM_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests/cpp)
endif()
