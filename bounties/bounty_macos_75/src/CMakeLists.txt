cmake_minimum_required(VERSION 3.10)
project(RustChainMacOSValidator C)

add_executable(MacOSValidator
    macos_validator.c
    macos_validator.h
)

set_target_properties(MacOSValidator PROPERTIES
    MACOSX_BUNDLE TRUE
)

target_link_libraries(MacOSValidator "-framework CoreServices" "-framework Carbon")
