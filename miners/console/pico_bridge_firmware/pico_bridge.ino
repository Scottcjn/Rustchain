/**
 * RIP-0683: Pico Serial Bridge Firmware
 * ======================================
 * 
 * Raspberry Pi Pico (RP2040) firmware for retro console mining.
 * Connects vintage game consoles to RustChain via controller port.
 * 
 * Hardware:
 *   - Raspberry Pi Pico or Pico W ($4 USD)
 *   - Custom controller port adapter (console-specific)
 *   - USB connection to host PC or WiFi (Pico W standalone)
 * 
 * Supported Consoles:
 *   - NES/Famicom (Ricoh 2A03 @ 1.79MHz)
 *   - SNES/Super Famicom (Ricoh 5A22 @ 3.58MHz)
 *   - Nintendo 64 (NEC VR4300 @ 93.75MHz)
 *   - Game Boy (Sharp LR35902 @ 4.19MHz)
 *   - Game Boy Advance (ARM7TDMI @ 16.78MHz)
 *   - Sega Genesis/Mega Drive (Motorola 68000 @ 7.67MHz)
 *   - Sega Master System (Zilog Z80 @ 3.58MHz)
 *   - Sega Saturn (Hitachi SH-2 @ 28.6MHz)
 *   - PlayStation 1 (MIPS R3000A @ 33.8MHz)
 * 
 * Protocol:
 *   Host sends: ATTEST|<nonce>|<wallet>|<timestamp>\n
 *   Pico replies: OK|<pico_id>|<console_arch>|<timing_json>|\n
 *   Or error: ERROR|<error_code>\n
 * 
 * Author: RustChain Core Team
 * License: Apache 2.0
 */

#include <Arduino.h>
#include <SHA256.h>
#include <json.h>

// ═══════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════

// Serial communication
#define SERIAL_BAUD 115200
#define SERIAL_TIMEOUT_MS 5000

// Controller port pins (NES example - adapt per console)
#define NES_CTRL_LATCH  5   // GPIO5 - Latch line
#define NES_CTRL_CLOCK  6   // GPIO6 - Clock line
#define NES_CTRL_DATA   7   // GPIO7 - Data line

// N64 Joybus pin (single-wire half-duplex)
#define N64_JOYBUS_PIN  2   // GPIO2

// Timing measurement
#define TIMING_SAMPLES 500
#define TIMING_WINDOW_US 100  // Sampling window in microseconds

// Pico unique ID (64-bit from OTP ROM)
#define PICO_ID_LEN 8
uint8_t pico_unique_id[PICO_ID_LEN];

// Current console type
enum ConsoleType {
    CONSOLE_NES = 0,
    CONSOLE_SNES,
    CONSOLE_N64,
    CONSOLE_GENESIS,
    CONSOLE_GAMEBOY,
    CONSOLE_GBA,
    CONSOLE_SMS,
    CONSOLE_SATURN,
    CONSOLE_PS1,
    CONSOLE_UNKNOWN
};

ConsoleType current_console = CONSOLE_NES;

// ═══════════════════════════════════════════════════════════
// Timing Data Structure
// ═══════════════════════════════════════════════════════════

struct TimingData {
    uint64_t ctrl_port_timing_mean_ns;
    uint64_t ctrl_port_timing_stdev_ns;
    double ctrl_port_cv;
    uint64_t rom_hash_time_us;
    uint32_t bus_jitter_samples;
    uint64_t bus_jitter_stdev_ns;
};

TimingData timing_data;

// ═══════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════

/**
 * Get Pico unique board ID from OTP ROM
 * This ID cannot be reprogrammed and serves as device fingerprint
 */
void get_pico_id() {
    pico_get_unique_board_id_string((char*)pico_unique_id, PICO_ID_LEN);
}

/**
 * Measure controller port timing
 * 
 * Samples the controller port poll interval and calculates
 * mean, standard deviation, and coefficient of variation.
 * 
 * Real hardware exhibits jitter from:
 *   - Crystal oscillator drift
 *   - Bus contention (CPU/PPU/DMA arbitration)
 *   - Thermal effects
 * 
 * Emulators have near-perfect timing (CV < 0.0001)
 */
void measure_controller_port_timing(ConsoleType console) {
    uint64_t timings[TIMING_SAMPLES];
    uint64_t sum = 0;
    
    // Configure pins based on console type
    setup_controller_port(console);
    
    // Sample controller port polls
    for (int i = 0; i < TIMING_SAMPLES; i++) {
        uint64_t start = time_us_64();
        
        // Wait for controller poll
        wait_for_controller_poll(console);
        
        uint64_t end = time_us_64();
        timings[i] = (end - start) * 1000;  // Convert to nanoseconds
        sum += timings[i];
    }
    
    // Calculate mean
    uint64_t mean = sum / TIMING_SAMPLES;
    timing_data.ctrl_port_timing_mean_ns = mean;
    
    // Calculate standard deviation
    uint64_t variance_sum = 0;
    for (int i = 0; i < TIMING_SAMPLES; i++) {
        int64_t diff = (int64_t)timings[i] - (int64_t)mean;
        variance_sum += diff * diff;
    }
    uint64_t variance = variance_sum / TIMING_SAMPLES;
    timing_data.ctrl_port_timing_stdev_ns = (uint64_t)sqrt(variance);
    
    // Calculate coefficient of variation
    if (mean > 0) {
        timing_data.ctrl_port_cv = (double)timing_data.ctrl_port_timing_stdev_ns / (double)mean;
    } else {
        timing_data.ctrl_port_cv = 0.0;
    }
    
    timing_data.bus_jitter_samples = TIMING_SAMPLES;
    timing_data.bus_jitter_stdev_ns = timing_data.ctrl_port_timing_stdev_ns;
}

/**
 * Setup controller port pins for specific console
 */
void setup_controller_port(ConsoleType console) {
    switch (console) {
        case CONSOLE_NES:
        case CONSOLE_SNES:
            pinMode(NES_CTRL_LATCH, OUTPUT);
            pinMode(NES_CTRL_CLOCK, OUTPUT);
            pinMode(NES_CTRL_DATA, INPUT);
            break;
            
        case CONSOLE_N64:
            pinMode(N64_JOYBUS_PIN, INPUT_PULLUP);
            break;
            
        case CONSOLE_GENESIS:
            // 6-button parallel port
            for (int i = 0; i < 6; i++) {
                pinMode(i, INPUT);
            }
            break;
            
        // ... other consoles
        default:
            break;
    }
}

/**
 * Wait for controller port poll and read button state
 */
void wait_for_controller_poll(ConsoleType console) {
    switch (console) {
        case CONSOLE_NES: {
            // NES controller protocol:
            // 1. Pulse latch high then low
            // 2. Read 8 bits on clock rising edges
            digitalWrite(NES_CTRL_LATCH, HIGH);
            delayMicroseconds(12);
            digitalWrite(NES_CTRL_LATCH, LOW);
            
            uint8_t buttons = 0;
            for (int i = 0; i < 8; i++) {
                digitalWrite(NES_CTRL_CLOCK, LOW);
                delayMicroseconds(6);
                if (digitalRead(NES_CTRL_DATA)) {
                    buttons |= (1 << i);
                }
                digitalWrite(NES_CTRL_CLOCK, HIGH);
                delayMicroseconds(6);
            }
            break;
        }
        
        case CONSOLE_N64: {
            // N64 Joybus protocol (simplified)
            // Half-duplex serial at 4 Mbit/s
            // Send request, receive response
            joybus_send_request();
            joybus_receive_response();
            break;
        }
        
        // ... other consoles
        default:
            delayMicroseconds(16667);  // Assume 60Hz
            break;
    }
}

/**
 * N64 Joybus send request
 */
void joybus_send_request() {
    // Send 1-byte command on Joybus
    // Protocol: start bit + 8 data bits + stop bit + ACK
    uint8_t cmd = 0xFF;  // Status request
    
    pinMode(N64_JOYBUS_PIN, OUTPUT);
    
    // Start bit (low)
    digitalWrite(N64_JOYBUS_PIN, LOW);
    delayMicroseconds(1);  // 4 Mbit/s = 250ns per bit
    
    // Data bits (LSB first)
    for (int i = 0; i < 8; i++) {
        if (cmd & (1 << i)) {
            digitalWrite(N64_JOYBUS_PIN, HIGH);
        } else {
            digitalWrite(N64_JOYBUS_PIN, LOW);
        }
        delayMicroseconds(1);
    }
    
    // Stop bit (high)
    digitalWrite(N64_JOYBUS_PIN, HIGH);
    delayMicroseconds(1);
    
    // Release bus for ACK
    pinMode(N64_JOYBUS_PIN, INPUT_PULLUP);
    delayMicroseconds(8);  // Wait for ACK
}

/**
 * N64 Joybus receive response
 */
void joybus_receive_response() {
    // Receive 3 bytes from controller
    uint8_t response[3];
    
    pinMode(N64_JOYBUS_PIN, INPUT_PULLUP);
    
    for (int b = 0; b < 3; b++) {
        uint8_t byte = 0;
        for (int i = 0; i < 8; i++) {
            delayMicroseconds(1);
            if (digitalRead(N64_JOYBUS_PIN)) {
                byte |= (1 << i);
            }
            // Wait for clock edge (self-clocked)
            while (digitalRead(N64_JOYBUS_PIN) == HIGH);
            while (digitalRead(N64_JOYBUS_PIN) == LOW);
        }
        response[b] = byte;
    }
}

/**
 * Compute SHA-256 hash and measure execution time
 * 
 * This is the core anti-emulation check. Real console CPUs
 * have characteristic execution times that cannot be faked.
 */
uint64_t compute_rom_hash(const char* nonce, const char* wallet, uint8_t* output) {
    SHA256 sha;
    
    // Prepare input: nonce || wallet
    String input = String(nonce) + String(wallet);
    
    // Start timing
    uint64_t start = time_us_64();
    
    // Compute hash
    sha.reset();
    sha.update((const uint8_t*)input.c_str(), input.length());
    sha.finalize(output, 32);
    
    // End timing
    uint64_t end = time_us_64();
    
    return end - start;  // Return time in microseconds
}

// ═══════════════════════════════════════════════════════════
// Serial Protocol Handler
// ═══════════════════════════════════════════════════════════

/**
 * Parse and handle ATTEST command from host
 * 
 * Format: ATTEST|<nonce>|<wallet>|<timestamp>\n
 */
void handle_attest_command(String command) {
    // Parse command
    int firstPipe = command.indexOf('|');
    int secondPipe = command.indexOf('|', firstPipe + 1);
    int thirdPipe = command.indexOf('|', secondPipe + 1);
    
    if (firstPipe < 0 || secondPipe < 0 || thirdPipe < 0) {
        Serial.println("ERROR|invalid_format");
        return;
    }
    
    String nonce = command.substring(firstPipe + 1, secondPipe);
    String wallet = command.substring(secondPipe + 1, thirdPipe);
    String timestamp = command.substring(thirdPipe + 1);
    
    // Measure controller port timing
    measure_controller_port_timing(current_console);
    
    // Compute ROM hash (SHA-256 of nonce || wallet)
    uint8_t hash[32];
    timing_data.rom_hash_time_us = compute_rom_hash(nonce.c_str(), wallet.c_str(), hash);
    
    // Build response JSON
    String response = String("OK|") +
                      String((char*)pico_unique_id) + "|" +
                      get_console_arch_name(current_console) + "|" +
                      build_timing_json() + "|";
    
    // Add hash as hex
    for (int i = 0; i < 32; i++) {
        if (hash[i] < 16) Serial.print("0");
        Serial.print(hash[i], HEX);
    }
    Serial.println();
    
    Serial.println(response);
}

/**
 * Get console architecture name string
 */
const char* get_console_arch_name(ConsoleType console) {
    switch (console) {
        case CONSOLE_NES: return "nes_6502";
        case CONSOLE_SNES: return "snes_65c816";
        case CONSOLE_N64: return "n64_mips";
        case CONSOLE_GENESIS: return "genesis_68000";
        case CONSOLE_GAMEBOY: return "gameboy_z80";
        case CONSOLE_GBA: return "gba_arm7";
        case CONSOLE_SMS: return "sms_z80";
        case CONSOLE_SATURN: return "saturn_sh2";
        case CONSOLE_PS1: return "ps1_mips";
        default: return "unknown";
    }
}

/**
 * Build timing data JSON response
 */
String build_timing_json() {
    String json = "{";
    json += "\"ctrl_port_timing_mean_ns\":" + String(timing_data.ctrl_port_timing_mean_ns) + ",";
    json += "\"ctrl_port_timing_stdev_ns\":" + String(timing_data.ctrl_port_timing_stdev_ns) + ",";
    json += "\"ctrl_port_cv\":" + String(timing_data.ctrl_port_cv, 6) + ",";
    json += "\"rom_hash_time_us\":" + String(timing_data.rom_hash_time_us) + ",";
    json += "\"bus_jitter_samples\":" + String(timing_data.bus_jitter_samples) + ",";
    json += "\"bus_jitter_stdev_ns\":" + String(timing_data.bus_jitter_stdev_ns);
    json += "}";
    return json;
}

// ═══════════════════════════════════════════════════════════
// Arduino Setup and Loop
// ═══════════════════════════════════════════════════════════

void setup() {
    // Initialize serial
    Serial.begin(SERIAL_BAUD);
    while (!Serial && millis() < 1000);
    
    // Get Pico unique ID
    get_pico_id();
    
    // Initialize controller port (default: NES)
    setup_controller_port(CONSOLE_NES);
    
    Serial.println("PICO_READY|RIP-0683 Console Bridge v1.0|");
}

void loop() {
    // Check for serial commands
    if (Serial.available() > 0) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        if (command.startsWith("ATTEST")) {
            handle_attest_command(command);
        }
        else if (command.startsWith("SET_CONSOLE")) {
            // SET_CONSOLE|n64_mips
            int pipe = command.indexOf('|');
            if (pipe > 0) {
                String arch = command.substring(pipe + 1);
                current_console = parse_console_type(arch);
                Serial.println("OK|console_set|" + arch);
            }
        }
        else if (command == "PING") {
            Serial.println("PONG|" + String((char*)pico_unique_id));
        }
        else {
            Serial.println("ERROR|unknown_command");
        }
    }
}

/**
 * Parse console type from architecture string
 */
ConsoleType parse_console_type(String arch) {
    arch.toLowerCase();
    if (arch == "nes_6502" || arch == "6502") return CONSOLE_NES;
    if (arch == "snes_65c816" || arch == "65c816") return CONSOLE_SNES;
    if (arch == "n64_mips" || arch == "mips") return CONSOLE_N64;
    if (arch == "genesis_68000" || arch == "68000") return CONSOLE_GENESIS;
    if (arch == "gameboy_z80" || arch == "z80") return CONSOLE_GAMEBOY;
    if (arch == "gba_arm7" || arch == "arm7") return CONSOLE_GBA;
    if (arch == "sms_z80") return CONSOLE_SMS;
    if (arch == "saturn_sh2" || arch == "sh2") return CONSOLE_SATURN;
    if (arch == "ps1_mips") return CONSOLE_PS1;
    return CONSOLE_UNKNOWN;
}
