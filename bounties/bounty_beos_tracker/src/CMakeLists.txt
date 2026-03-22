cmake_minimum_required(VERSION 3.10)
project(RustChainBeOSValidator CXX)

set(CMAKE_CXX_STANDARD 11)

find_package(BeOS REQUIRED)

add_executable(RustChainValidator
    main.cpp
)

target_link_libraries(RustChainValidator beos)
install(TARGETS RustChainValidator DESTINATION apps)
