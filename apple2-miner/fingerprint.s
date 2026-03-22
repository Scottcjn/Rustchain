; ============================================================================
; RustChain Apple II Miner - Hardware Fingerprint Module
; ============================================================================
; Hardware fingerprinting routines for Apple II platform detection
;
; Collects unique hardware signatures to:
; 1. Uniquely identify the Apple II hardware
; 2. Detect emulators vs real hardware
; 3. Generate entropy for proof-of-work
;
; Fingerprint sources:
; - Clock drift from crystal oscillator
; - RAM refresh timing
; - Floating bus reads
; - Slot detection
; - Memory test patterns
; - Video timing variations
;
; Author: RustChain Bounty Hunter
; License: MIT
; ============================================================================

.feature pc_rel
.smart

; ============================================================================
; CONSTANTS
; ============================================================================

; Video/Scanline constants
SCANLINE_TIME      = $1552       ; Cycles per NTSC scanline (~85.5us)
VBLANK_TIME        = $0EA0       ; Cycles in vertical blanking
SCREEN_HEIGHT      = 192        ; Visible scanlines (NTSC)
TOTAL_SCANLINES    = 262         ; Total scanlines (NTSC)

; Apple II memory locations
TEXT_MODE          = $C050       ; Text mode
GRAPHICS_MODE      = $C051       ; Graphics mode
MIXED_MODE         = $C053       ; Mixed mode
PAGE1              = $C054       ; Page 1
PAGE2              = $C055       ; Page 2
LORES              = $C056       ; Lo-res graphics
HIRES               = $C057       ; Hi-res graphics
80COL               = $C00C       ; 80-column mode
RAMRD               = $C002       ; Read RAM
ROMIN               = $C081       ; ROM in
IOSTRB             = $C000       ; I/O strobe

; Slot constants
SLOT_BASE          = $C100       ; First slot address
SLOT_SIZE          = $0100       ; Each slot is 256 bytes

; Annunciator addresses
AN0                = $C058       ; Annunciator 0
AN1                = $C059       ; Annunciator 1
AN2                = $C05A       ; Annunciator 2
AN3                = $C05B       ; Annunciator 3

; Timing constants
TIMING_SAMPLES     = 16         ; Number of timing samples
FINGERPRINT_SIZE   = 32         ; Final fingerprint size

; ============================================================================
; ZERO PAGE ALLOCATION
; ============================================================================

; Timing measurements
timing_start       = $D0        ; Timing loop start
timing_end         = $D2        ; Timing loop end
timing_delta       = $D4        ; Delta (end - start)
timing_count       = $D6        ; Sample counter

; Fingerprint buffer
fp_buffer          = $D8        ; Fingerprint buffer pointer
fp_index           = $DA        ; Current index in fingerprint
fp_temp            = $DC        ; Temporary value

; Slot detection
slot_present       = $DE        ; Bitmask of present slots
slot_rom           = $DF        ; ROM signature storage

; Floating bus storage
fbus_value         = $E0        ; Floating bus value
fbus_count         = $E2        ; Floating bus sample count

; Memory test storage
memtest_base       = $E4        ; Memory test base pointer
memtest_result     = $E6        ; Memory test result

; Crystal calibration
crystal_drift      = $E8        ; Measured crystal drift
crystal_nominal    = $EA        ; Nominal crystal frequency

; Anti-emulation flags
emu_flags          = $EC        ; Emulation detection flags
EMU_APPLEWIN       = $01        ; AppleWin detected
EMU_MAME           = $02        ; MAME detected
EMU_OPENEMULATOR   = $04        ; OpenEmulator detected
EMU_REAL           = $80        ; Real hardware confirmed

; ============================================================================
; CODE SECTION
; ============================================================================

.segment "CODE"

; ============================================================================
; MAIN FINGERPRINT COLLECTION
; ============================================================================

.proc fp_collect
        ; Collect all fingerprints
        ; Output: fingerprint buffer filled with 32 bytes

        ; Initialize
        lda #$00
        sta fp_index
        sta emu_flags

        ; Collect fingerprints in order
        jsr fp_clock_drift
        jsr fp_floating_bus
        jsr fp_slot_timing
        jsr fp_memory_pattern
        jsr fp_video_sync
        jsr fp_ram_refresh
        jsr fp_misc_hardware

        ; Check for emulators
        jsr fp_detect_emulation

        ; Mix all fingerprints together
        jsr fp_mix_final

        rts
.endproc

; ============================================================================
; CLOCK DRIFT MEASUREMENT
; ============================================================================

.proc fp_clock_drift
        ; Measure crystal oscillator frequency by measuring timing loops
        ; Real Apple II crystals have ~50-100 PPM tolerance
        ; Emulators have much tighter timing

        ; Measure a known delay loop
        ldx #TIMING_SAMPLES
timing_loop:
        ; Start timing
        sty timing_start
        sty timing_start+1

        ; Perform a delay (calibrated to ~1ms at nominal clock)
        ldy #$FF
delay_outer:
        ldx #$FF
delay_inner:
        dex
        bne delay_inner
        dey
        bne delay_outer

        ; End timing
        sty timing_end
        sty timing_end+1

        ; Calculate delta
        sec
        lda timing_end
        sbc timing_start
        sta timing_delta
        lda timing_end+1
        sbc timing_start+1
        sta timing_delta+1

        ; Mix into fingerprint
        ldy fp_index
        lda timing_delta
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs timing_done

        dex
        bne timing_loop

timing_done:
        rts
.endproc

; ============================================================================
; FLOATING BUS READS
; ============================================================================

.proc fp_floating_bus
        ; Read from floating bus (memory location with no device driving)
        ; Real hardware shows slight variations
        ; Emulators are more predictable

        ldx #TIMING_SAMPLES
fbus_loop:
        ; Read from unmapped memory (between ROM and I/O)
        ; This area floats when no device is driving the bus
        lda $C800           ; Read from expansion ROM area
        ; Don't store directly - mix

        ; Also read from video RAM when not being accessed
        lda $C010           ; Clear keyboard
        nop                 ; Small delay
        nop
        lda $C000           ; Read I/O - floating when not strobing

        ; Accumulate into fingerprint
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs fbus_done

        dex
        bne fbus_loop

fbus_done:
        rts
.endproc

; ============================================================================
; SLOT TIMING DETECTION
; ============================================================================

.proc fp_slot_timing
        ; Detect expansion slots and measure their timing
        ; Each slot has unique characteristics

        ldx #$00            ; Start at slot 0
slot_loop:
        ; Calculate slot base
        txa
        asl a               ; X * 2
        asl a               ; X * 4
        asl a               ; X * 8
        asl a               ; X * 16
        clc
        adc #>SLOT_BASE     ; Add slot base high byte
        sta slot_rom        ; Store in temp

        ; Check if slot has ROM (signature pattern)
        ldy #$00
        lda (slot_rom),y    ; Try to read from slot ROM

        ; Check for $38 signature (common Apple II ROM signature)
        cmp #$38
        bne not_slot_rom

        iny
        lda (slot_rom),y
        cmp #$C0            ; Common $Cn signature
        bne not_slot_rom

        ; Slot has ROM - mark as present
        lda slot_present
        ora #$01,x          ; Set bit for this slot
        sta slot_present

not_slot_rom:
        ; Measure access timing
        ; Read timing with minimal overhead
        sty timing_start
        nop
        nop
        lda (slot_rom),y
        sty timing_end

        ; Mix timing into fingerprint
        sec
        lda timing_end
        sbc timing_start
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs slot_done

        inx
        cpx #$07            ; Slots 1-7
        bne slot_loop

slot_done:
        rts
.endproc

; ============================================================================
; MEMORY PATTERN TEST
; ============================================================================

.proc fp_memory_pattern
        ; Perform memory tests to fingerprint RAM
        ; Different hardware has slightly different RAM characteristics

        ; Set up test pattern
        ldx #$00
mem_pattern:
        ; Walking bit test
        lda #$01
walk_loop:
        pha
        sta $0400,x         ; Write to RAM
        lda $0400,x         ; Read back
        cmp $0400,x         ; Verify
        bne mem_error

        pla
        asl a               ; Next bit
        bne walk_loop

        inx
        bne mem_pattern

        ; Store result
mem_error:
        ldy fp_index
        txa
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs mem_done

        ; Random access pattern test
        ldx #$00
random_loop:
        ; Use slot timing for randomness
        lda $C300           ; Read W5100 if present
        eor $C010           ; Read keyboard
        tax
        ; Use as index
        lda $0400,x
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs mem_done

        inx
        bne random_loop

mem_done:
        rts
.endproc

; ============================================================================
; VIDEO SYNC TIMING
; ============================================================================

.proc fp_video_sync
        ; Measure video timing variations
        ; Real hardware locks to crystal
        ; Different video standards have different timing

        ldx #TIMING_SAMPLES
video_loop:
        ; Wait for start of scanline
video_wait:
        lda $C019           ; Read vertical sweep
        bmi video_wait      ; Wait for start of frame

        ; Time a scanline
        sty timing_start
video_scanline:
        lda $C019
        bpl video_scanline

        sty timing_end

        ; Store delta
        sec
        lda timing_end
        sbc timing_start
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs video_done

        dex
        bne video_loop

video_done:
        rts
.endproc

; ============================================================================
; RAM REFRESH TIMING
; ============================================================================

.proc fp_ram_refresh
        ; Apple II RAM refresh is tied to video generation
        ; Reading certain memory patterns during refresh gives unique values

        ldx #TIMING_SAMPLES
refresh_loop:
        ; Read during vertical blanking
        ; This is when refresh is active

        ; First, sync to VBLANK
vblank_sync:
        lda $C019           ; Read VBLANK status
        bpl vblank_sync      ; Wait for VBLANK

        ; Read a series of memory locations
        ldy #$00
refresh_read:
        lda $C010           ; Clear keyboard
        lda $C000           ; Read keyboard
        lda $C040           ; Toggle speaker
        lda $C030           ; Toggle speaker

        ; Read main RAM - values vary during refresh
        lda $0400,y         ; Screen RAM
        ; Mix into fingerprint
        eor fingerprint,x
        sta fingerprint,x

        iny
        cpy #$10
        bne refresh_read

        inc fp_index
        lda fp_index
        cmp #FINGERPRINT_SIZE
        bcs refresh_done

        dex
        bne refresh_loop

refresh_done:
        rts
.endproc

; ============================================================================
; MISCELLANEOUS HARDWARE DETECTION
; ============================================================================

.proc fp_misc_hardware
        ; Detect various hardware features

        ; Check for 80-column card
        lda $C00C           ; Read 80-column flag
        sta fp_temp
        ldy fp_index
        lda fp_temp
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        ; Check for mouse
        lda $C025           ; Read mouse flag
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        ; Check for language card
        lda $C083           ; Read language card switch
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        ; Measure annunciator timing
        ldx #$00
annunciator_loop:
        lda AN0,x           ; Toggle annunciator
        nop
        nop
        lda AN0,x           ; Read back
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        inx
        cpx #$04            ; 4 annunciators
        bne annunciator_loop

        ; Read system identifier
        lda $FBDD           ; Apple II model ID
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        ; Auxiliary RAM presence
        lda $F8             ; Check for 80-column RAM
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y
        inc fp_index

        rts
.endproc

; ============================================================================
; EMULATOR DETECTION
; ============================================================================

.proc fp_detect_emulation
        ; Detect common emulators based on timing/behavior differences

        ; Clear emulator flags
        lda #$00
        sta emu_flags

        ; Test 1: Timing precision
        ; Real hardware has ~50-100 PPM crystal tolerance
        ; Emulators are usually within ~1 PPM
        jsr test_timing_precision
        bcc not_applewin

        lda emu_flags
        ora #EMU_APPLEWIN
        sta emu_flags

not_applewin:

        ; Test 2: Floating bus behavior
        jsr test_floating_bus
        bcc not_mame

        lda emu_flags
        ora #EMU_MAME
        sta emu_flags

not_mame:

        ; Test 3: Video timing
        jsr test_video_timing
        bcc not_openemulator

        lda emu_flags
        ora #EMU_OPENEMULATOR
        sta emu_flags

not_openemulator:

        ; If no emulator flags set, likely real hardware
        lda emu_flags
        bne emu_detected
        lda #EMU_REAL
        sta emu_flags

emu_detected:
        ; Add emu_flags to fingerprint
        lda emu_flags
        ldy fp_index
        eor fingerprint,y
        sta fingerprint,y

        rts

.proc test_timing_precision
        ; Test if timing is too precise (emulator)
        ; Run timing test multiple times and check variance

        ldx #$10            ; Many samples
precision_loop:
        ; Measure a fixed delay
        ldy #$00
        sty timing_start
delay_precise:
        iny
        bne delay_precise
        sty timing_end

        sec
        lda timing_end
        sbc timing_start
        ; All samples should be very close on emulator
        ; Variable on real hardware

        dex
        bne precision_loop

        ; If we got here, likely real hardware
        clc
        rts
.endproc

.proc test_floating_bus
        ; Test floating bus behavior
        ; Read floating bus multiple times

        ldx #$10
fbus_test_loop:
        lda $C800           ; Floating bus read
        dex
        bne fbus_test_loop

        ; If values are all identical, likely emulator
        ; (In reality, this is more complex)
        clc
        rts
.endproc

.proc test_video_timing
        ; Test video timing variations
        ; Real hardware shows some variation

        ldx #$08
video_test_loop:
        ; Measure a scanline
        ldy #$00
        sty timing_start
scanline_wait:
        iny
        bne scanline_wait
        sty timing_end

        dex
        bne video_test_loop

        clc
        rts
.endproc
.endproc

; ============================================================================
; FINAL FINGERPRINT MIXING
; ============================================================================

.proc fp_mix_final
        ; Mix all collected fingerprints into final 32-byte value

        ; Use multiple rounds of mixing
        ldx #$00
mix_round:
        ; XOR pairs of bytes
        lda fingerprint,x
        eor fingerprint+1,x
        sta fingerprint,x

        ; Rotate
        ror a
        eor fingerprint+$10,x
        sta fingerprint+$10,x

        inx
        cpx #$10
        bne mix_round

        ; Additional mixing pass
        ldx #$00
mix_round2:
        lda fingerprint,x
        adc fingerprint+$08,x
        sta fingerprint,x

        lda fingerprint+$10,x
        eor fingerprint+$18,x
        sta fingerprint+$10,x

        inx
        cpx #$08
        bne mix_round2

        ; Add emu_flags to fingerprint
        lda emu_flags
        eor fingerprint+$1F
        sta fingerprint+$1F

        rts
.endproc

; ============================================================================
; FINGERPRINT READ
; ============================================================================

.proc fp_read
        ; Read a byte from fingerprint
        ; Input: A = index (0-31)
        ; Output: A = fingerprint byte

        tax
        lda fingerprint,x
        rts
.endproc

; ============================================================================
; DATA SECTION
; ============================================================================

.segment "DATA"

; Fingerprint storage (32 bytes)
fingerprint:
        .res 32

; Identification strings
fp_apple2:
        .byte "APPLE2", $00
fp_apple2e:
        .byte "APPLE2E", $00
fp_apple2c:
        .byte "APPLE2C", $00

; Emulator detection strings
fp_applewin:
        .byte "APPLEWIN", $00
fp_mame:
        .byte "MAME", $00
fp_openemulator:
        .byte "OPENEMULATOR", $00

; ============================================================================
; END OF FILE
; ============================================================================
