/*
 * RustChain Miner for UNIVAC I
 * 
 * Target: UNIVAC I (1951) - First Commercial Computer
 * Architecture: Serial Decimal, Mercury Delay Line Memory
 * Clock: 2.25 MHz
 * Memory: 12 KB (12,288 bits) via 128 mercury delay lines
 * 
 * This miner is designed for the unique architecture of UNIVAC I:
 * - Decimal arithmetic (not binary!)
 * - Serial computation
 * - Mercury delay line memory with 500 μs access time
 * - Magnetic tape I/O
 * - 5,000 vacuum tubes
 *
 * Build: UNIVAC I Assembler (1951) or SIMH cross-assembler
 *   unassembler src/miner_main.s -o miner.bin
 *
 * Note: This is primarily a conceptual/historical implementation.
 * Only 46 UNIVAC I systems were ever built, most are in museums.
 * Real hardware required for bounty rewards.
 */

/* ============================================================================
 * SYMBOL DEFINITIONS
 * ============================================================================ */

        .ENTRY  MINER_START,0000
        .ENTRY  MINER_VERSION,0002

/* Version information */
VERSION_MAJOR     .EQU  0
VERSION_MINOR     .EQU  1
VERSION_PATCH     .EQU  0

/* Memory allocation (delay lines) */
DELAY_LINE_SYSTEM    .EQU  0    /* Delay lines 0-3: System */
DELAY_LINE_CODE      .EQU  4    /* Delay lines 4-7: Program code */
DELAY_LINE_DATA      .EQU  8    /* Delay lines 8-11: Data */
DELAY_LINE_NETWORK   .EQU  12   /* Delay lines 12-15: Network buffer */
DELAY_LINE_EXTENDED  .EQU  16   /* Delay lines 16+: Extended */

/* I/O device codes */
DEVICE_TAPE      .EQU  1
DEVICE_CONSOLE   .EQU  2
DEVICE_PRINTER   .EQU  3

/* Status codes */
STATUS_OK        .EQU  0
STATUS_ERROR     .EQU  1
STATUS_EMULATOR  .EQU  2

/* ============================================================================
 * MAIN ENTRY POINT
 * ============================================================================ */

MINER_START:
        /* Initialize system */
        CALL    INIT_SYSTEM
        
        /* Print banner */
        CALL    PRINT_BANNER
        
        /* Parse arguments (from console switches) */
        CALL    PARSE_ARGS
        
        /* Check wallet address */
        L       WALLET_ADDR
        JZ      ERROR_NO_WALLET
        
        /* Initialize hardware detection */
        CALL    HW_UNIVAC_INIT
        
        /* Generate miner ID from hardware fingerprint */
        CALL    GENERATE_MINER_ID
        
        /* Print miner ID */
        L       MINER_ID
        CALL    PRINT_STRING
        
        /* Run emulator detection */
        CALL    DETECT_EMULATOR
        JZ      REAL_HARDWARE
        
        /* Emulator detected - warn but continue */
        CALL    PRINT_EMULATOR_WARNING
        
REAL_HARDWARE:
        /* Initialize network (via tape/serial bridge) */
        CALL    NETWORK_INIT
        
        /* Perform hardware attestation */
        CALL    ATTEST_TO_NODE
        
        /* Start mining loop */
        CALL    MINING_LOOP
        
        /* Cleanup and exit */
        CALL    CLEANUP
        STOP

ERROR_NO_WALLET:
        /* Display error: wallet required */
        L       MSG_NO_WALLET
        CALL    PRINT_STRING
        STOP

/* ============================================================================
 * PRINT BANNER
 * ============================================================================ */

PRINT_BANNER:
        /* Save return address */
        STORE   RA, PRINT_BANNER_RA
        
        /* Print ASCII art banner */
        L       BANNER_LINE1
        CALL    PRINT_STRING
        L       BANNER_LINE2
        CALL    PRINT_STRING
        L       BANNER_LINE3
        CALL    PRINT_STRING
        L       BANNER_LINE4
        CALL    PRINT_STRING
        L       BANNER_VERSION
        CALL    PRINT_STRING
        
        /* Restore return address */
        LOAD    PRINT_BANNER_RA
        RETURN

/* Banner strings (stored in delay lines) */
BANNER_LINE1:   .STRING "  _  _  ____  ____  ____  ___  ____  ____ "
BANNER_LINE2:   .STRING " / )( \(  __)(  _ \(  _ \/ __)(  _ \(  __)"
BANNER_LINE3:   .STRING " ) \/ ( ) _)  )   / )___/\__ \ )   / ) _) "
BANNER_LINE4:   .STRING " \____/(____)(__\_)(__)  (___/(__\_)(____)"
BANNER_VERSION: .STRING "        UNIVAC I Miner v0.1.0"

/* ============================================================================
 * PARSE ARGUMENTS
 * ============================================================================ */

PARSE_ARGS:
        STORE   RA, PARSE_ARGS_RA
        
        /* Read wallet from console switches */
        /* Wallet address entered via UNISCOPE console */
        CALL    READ_CONSOLE_SWITCHES
        
        /* Validate wallet format */
        L       WALLET_ADDR
        CALL    VALIDATE_WALLET
        JZ      WALLET_VALID
        
        /* Invalid wallet format */
        L       MSG_INVALID_WALLET
        CALL    PRINT_STRING
        STOP
        
WALLET_VALID:
        LOAD    PARSE_ARGS_RA
        RETURN

/* ============================================================================
 * HARDWARE INITIALIZATION
 * ============================================================================ */

INIT_SYSTEM:
        STORE   RA, INIT_SYSTEM_RA
        
        /* Initialize mercury delay lines */
        CALL    INIT_DELAY_LINES
        
        /* Warm up vacuum tubes (15 minutes typical) */
        /* In practice, UNIVAC I required warm-up before operation */
        CALL    CHECK_TUBE_WARMUP
        
        /* Initialize magnetic tape unit */
        CALL    INIT_TAPE_UNIT
        
        /* Clear memory */
        CALL    CLEAR_MEMORY
        
        LOAD    INIT_SYSTEM_RA
        RETURN

/* ============================================================================
 * MINING LOOP
 * ============================================================================ */

MINING_LOOP:
        STORE   RA, MINING_LOOP_RA
        
MINING_LOOP_START:
        /* Check for stop condition (console interrupt) */
        CALL    CHECK_CONSOLE_INTERRUPT
        JNZ     MINING_STOP
        
        /* Perform one mining iteration */
        CALL    MINING_ITERATION
        
        /* Print progress dot */
        L       CHAR_DOT
        CALL    PRINT_CHAR
        
        /* Delay (UNIVAC I is slow!) */
        CALL    DELAY_1_SECOND
        
        /* Loop back */
        JUMP    MINING_LOOP_START
        
MINING_STOP:
        /* Print shutdown message */
        L       MSG_SHUTDOWN
        CALL    PRINT_STRING
        
        LOAD    MINING_LOOP_RA
        RETURN

CHAR_DOT:       .STRING "."

/* ============================================================================
 * CLEANUP
 * ============================================================================ */

CLEANUP:
        /* Save mining state to tape */
        CALL    SAVE_STATE_TO_TAPE
        
        /* Close network connection */
        CALL    NETWORK_CLOSE
        
        /* Stop tape unit */
        CALL    STOP_TAPE_UNIT
        
        /* Print thank you message */
        L       MSG_THANKS
        CALL    PRINT_STRING
        
        STOP

/* ============================================================================
 * ERROR MESSAGES
 * ============================================================================ */

MSG_NO_WALLET:      .STRING "ERROR: Wallet address required!"
MSG_INVALID_WALLET: .STRING "ERROR: Invalid wallet format!"
MSG_EMULATOR:       .STRING "WARNING: Emulator detected! Rewards: 0 RTC"
MSG_SHUTDOWN:       .STRING "Miner shutting down..."
MSG_THANKS:         .STRING "Thank you for mining RustChain on UNIVAC I!"

/* ============================================================================
 * DATA STORAGE
 * ============================================================================ */

        .ORG  0200  /* Data segment in delay lines 8-11 */

WALLET_ADDR:    .BLOCK  64      /* Wallet address storage */
MINER_ID:       .BLOCK  64      /* Miner ID (hardware fingerprint) */
NODE_URL:       .BLOCK  128     /* Node URL */
MINING_STATE:   .BLOCK  256     /* Mining state buffer */
NETWORK_BUFFER: .BLOCK  512     /* Network I/O buffer */

        .ORG  0400  /* Continue program code */

/* ============================================================================
 * HARDWARE DETECTION ROUTINES (see hw_univac.s)
 * ============================================================================ */

        .EXTERN HW_UNIVAC_INIT
        .EXTERN GENERATE_MINER_ID
        .EXTERN DETECT_EMULATOR

/* ============================================================================
 * NETWORK ROUTINES (see network.s)
 * ============================================================================ */

        .EXTERN NETWORK_INIT
        .EXTERN NETWORK_CLOSE
        .EXTERN ATTEST_TO_NODE

/* ============================================================================
 * UTILITY ROUTINES (see utils.s)
 * ============================================================================ */

        .EXTERN INIT_DELAY_LINES
        .EXTERN CHECK_TUBE_WARMUP
        .EXTERN INIT_TAPE_UNIT
        .EXTERN STOP_TAPE_UNIT
        .EXTERN CLEAR_MEMORY
        .EXTERN READ_CONSOLE_SWITCHES
        .EXTERN VALIDATE_WALLET
        .EXTERN PRINT_STRING
        .EXTERN PRINT_CHAR
        .EXTERN PRINT_BANNER
        .EXTERN PRINT_EMULATOR_WARNING
        .EXTERN CHECK_CONSOLE_INTERRUPT
        .EXTERN MINING_ITERATION
        .EXTERN DELAY_1_SECOND
        .EXTERN SAVE_STATE_TO_TAPE

/* End of miner_main.s */
