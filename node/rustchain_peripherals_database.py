#!/usr/bin/env python3
"""
RustChain Peripherals Database - Proof of Antiquity Detection
Version: 1.1.0 - Rebalanced peripheral bonuses (much weaker)

Provides identification and SMALL bonus scoring for vintage peripherals.
Peripheral bonuses are intentionally tiny (0.001-0.01) to serve as
tie-breakers rather than major multiplier influences.

The real PoA multipliers come from CPUs - peripherals are just icing.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class PeripheralEntry:
    id: str
    name: str
    category: str
    year: int
    bonus: float  # Now 0.001-0.01 (0.1% to 1%) instead of 0.25-0.40
    rarity: str   # MYTHIC, LEGENDARY, RARE, UNCOMMON, COMMON
    notes: str = ""

# =============================================================================
# CD-ROM DRIVES - Tiny bonuses for rare optical drives
# =============================================================================
CDROM_DATABASE: Dict[str, PeripheralEntry] = {
    # Proprietary interface drives (rarest) - max 0.01 (1%)
    "mitsumi_lu005": PeripheralEntry("mitsumi_lu005", "Mitsumi LU005", "cdrom", 1992, 0.008, "LEGENDARY", "Proprietary interface"),
    "mitsumi_crmc_lu005s": PeripheralEntry("mitsumi_crmc_lu005s", "Mitsumi CRMC-LU005S", "cdrom", 1993, 0.007, "LEGENDARY", "Proprietary"),
    "philips_cm205": PeripheralEntry("philips_cm205", "Philips CM205", "cdrom", 1992, 0.008, "LEGENDARY", "LMS/Philips interface"),
    "philips_cm206": PeripheralEntry("philips_cm206", "Philips CM206", "cdrom", 1993, 0.007, "LEGENDARY", "LMS interface"),
    "sony_cdu31a": PeripheralEntry("sony_cdu31a", "Sony CDU31A", "cdrom", 1992, 0.007, "LEGENDARY", "Proprietary Sony"),
    "sony_cdu33a": PeripheralEntry("sony_cdu33a", "Sony CDU33A", "cdrom", 1993, 0.006, "RARE", "Proprietary Sony"),
    "panasonic_cr521": PeripheralEntry("panasonic_cr521", "Panasonic CR-521", "cdrom", 1992, 0.007, "LEGENDARY", "Proprietary SoundBlaster"),
    "panasonic_cr522": PeripheralEntry("panasonic_cr522", "Panasonic CR-522", "cdrom", 1993, 0.006, "RARE", "Proprietary"),
    "aztech_cda268": PeripheralEntry("aztech_cda268", "Aztech CDA-268", "cdrom", 1993, 0.006, "RARE", "Proprietary Aztech"),
    
    # Caddy-loading SCSI drives - 0.006-0.008
    "apple_cd150": PeripheralEntry("apple_cd150", "Apple CD-150", "cdrom", 1992, 0.007, "LEGENDARY", "Caddy SCSI"),
    "apple_cd300": PeripheralEntry("apple_cd300", "Apple CD-300", "cdrom", 1993, 0.006, "RARE", "Caddy SCSI 2x"),
    "nec_cdr73": PeripheralEntry("nec_cdr73", "NEC CDR-73", "cdrom", 1991, 0.007, "LEGENDARY", "Caddy SCSI"),
    "nec_cdr84": PeripheralEntry("nec_cdr84", "NEC CDR-84", "cdrom", 1993, 0.006, "RARE", "Caddy SCSI"),
    "toshiba_xm3301": PeripheralEntry("toshiba_xm3301", "Toshiba XM-3301", "cdrom", 1992, 0.006, "RARE", "Caddy SCSI"),
    "plextor_px43cs": PeripheralEntry("plextor_px43cs", "Plextor PX-43CS", "cdrom", 1995, 0.005, "RARE", "Caddy SCSI"),
    
    # Multi-disc changers - 0.006-0.007
    "nakamichi_mj516": PeripheralEntry("nakamichi_mj516", "Nakamichi MJ-5.16", "cdrom", 1995, 0.007, "LEGENDARY", "16-disc changer"),
    "pioneer_drm604x": PeripheralEntry("pioneer_drm604x", "Pioneer DRM-604X", "cdrom", 1994, 0.006, "RARE", "6-disc changer"),
    "nec_4x4": PeripheralEntry("nec_4x4", "NEC 4x4", "cdrom", 1995, 0.006, "RARE", "4-disc changer"),
    
    # Early tray-loading - 0.003-0.005
    "mitsumi_fxc": PeripheralEntry("mitsumi_fxc", "Mitsumi FX001", "cdrom", 1994, 0.004, "UNCOMMON", "Early IDE"),
    "creative_cd220e": PeripheralEntry("creative_cd220e", "Creative CD-220E", "cdrom", 1995, 0.003, "UNCOMMON", "2x IDE"),
    "acer_624a": PeripheralEntry("acer_624a", "Acer 624A", "cdrom", 1996, 0.003, "UNCOMMON", "6x IDE"),
    
    # Standard 90s drives - 0.001-0.002
    "generic_4x": PeripheralEntry("generic_4x", "Generic 4x CD-ROM", "cdrom", 1995, 0.002, "COMMON", "Standard 4x"),
    "generic_8x": PeripheralEntry("generic_8x", "Generic 8x CD-ROM", "cdrom", 1996, 0.002, "COMMON", "Standard 8x"),
    "generic_12x": PeripheralEntry("generic_12x", "Generic 12x CD-ROM", "cdrom", 1997, 0.001, "COMMON", "Standard"),
    "generic_24x": PeripheralEntry("generic_24x", "Generic 24x CD-ROM", "cdrom", 1998, 0.001, "COMMON", "Standard"),
    "generic_32x": PeripheralEntry("generic_32x", "Generic 32x CD-ROM", "cdrom", 1999, 0.001, "COMMON", "Standard"),
    "generic_52x": PeripheralEntry("generic_52x", "Generic 52x CD-ROM", "cdrom", 2000, 0.001, "COMMON", "Standard"),
}

# =============================================================================
# SOUND CARDS - Tiny bonuses for vintage audio
# =============================================================================
SOUND_CARD_DATABASE: Dict[str, PeripheralEntry] = {
    # Mythic tier sound cards - max 0.01 (1%)
    "gus_classic": PeripheralEntry("gus_classic", "Gravis UltraSound Classic", "sound", 1992, 0.010, "MYTHIC", "1MB wavetable"),
    "gus_max": PeripheralEntry("gus_max", "Gravis UltraSound MAX", "sound", 1994, 0.009, "MYTHIC", "1MB + codec"),
    "gus_pnp": PeripheralEntry("gus_pnp", "Gravis UltraSound PnP", "sound", 1995, 0.008, "LEGENDARY", "AMD InterWave"),
    "gus_ace": PeripheralEntry("gus_ace", "Gravis UltraSound ACE", "sound", 1995, 0.008, "LEGENDARY", "Budget GUS"),
    "mt32": PeripheralEntry("mt32", "Roland MT-32", "sound", 1987, 0.010, "MYTHIC", "LA synthesis"),
    "lapc1": PeripheralEntry("lapc1", "Roland LAPC-I", "sound", 1988, 0.010, "MYTHIC", "MT-32 on ISA"),
    "cm32l": PeripheralEntry("cm32l", "Roland CM-32L", "sound", 1989, 0.009, "MYTHIC", "Enhanced MT-32"),
    "cm64": PeripheralEntry("cm64", "Roland CM-64", "sound", 1989, 0.009, "MYTHIC", "CM-32L + CM-32P"),
    "sc55": PeripheralEntry("sc55", "Roland SC-55", "sound", 1991, 0.008, "LEGENDARY", "Sound Canvas"),
    "sc88": PeripheralEntry("sc88", "Roland SC-88", "sound", 1994, 0.007, "LEGENDARY", "Sound Canvas Pro"),
    "adlib": PeripheralEntry("adlib", "AdLib Music Card", "sound", 1987, 0.010, "MYTHIC", "Original OPL2"),
    "adlib_gold": PeripheralEntry("adlib_gold", "AdLib Gold 1000", "sound", 1992, 0.009, "MYTHIC", "OPL3 + surround"),
    
    # Legendary sound cards - 0.006-0.008
    "sb10": PeripheralEntry("sb10", "Sound Blaster 1.0", "sound", 1989, 0.008, "LEGENDARY", "Original SB"),
    "sb15": PeripheralEntry("sb15", "Sound Blaster 1.5", "sound", 1990, 0.007, "LEGENDARY", "DSP 1.05"),
    "sb20": PeripheralEntry("sb20", "Sound Blaster 2.0", "sound", 1991, 0.007, "LEGENDARY", "DSP 2.01"),
    "sbpro": PeripheralEntry("sbpro", "Sound Blaster Pro", "sound", 1991, 0.006, "RARE", "Dual OPL2"),
    "sbpro2": PeripheralEntry("sbpro2", "Sound Blaster Pro 2", "sound", 1992, 0.006, "RARE", "OPL3"),
    "sb16": PeripheralEntry("sb16", "Sound Blaster 16", "sound", 1992, 0.005, "RARE", "16-bit audio"),
    "sb16_asp": PeripheralEntry("sb16_asp", "Sound Blaster 16 ASP", "sound", 1993, 0.006, "RARE", "With ASP chip"),
    "awe32": PeripheralEntry("awe32", "Sound Blaster AWE32", "sound", 1994, 0.006, "RARE", "EMU8000"),
    "awe64": PeripheralEntry("awe64", "Sound Blaster AWE64", "sound", 1996, 0.005, "UNCOMMON", "EMU8000"),
    "awe64_gold": PeripheralEntry("awe64_gold", "Sound Blaster AWE64 Gold", "sound", 1996, 0.006, "RARE", "Gold edition"),
    
    # Rare/exotic sound cards - 0.006-0.008
    "mpu401": PeripheralEntry("mpu401", "Roland MPU-401", "sound", 1984, 0.008, "LEGENDARY", "MIDI interface"),
    "pas16": PeripheralEntry("pas16", "Pro Audio Spectrum 16", "sound", 1992, 0.006, "RARE", "MediaVision"),
    "aria_16": PeripheralEntry("aria_16", "Aria 16", "sound", 1993, 0.006, "RARE", "Sierra chipset"),
    "turtle_beach_multisound": PeripheralEntry("turtle_beach_multisound", "Turtle Beach MultiSound", "sound", 1993, 0.007, "LEGENDARY", "Motorola DSP"),
    "turtle_beach_monterey": PeripheralEntry("turtle_beach_monterey", "Turtle Beach Monterey", "sound", 1994, 0.006, "RARE", "Wavetable"),
    "turtle_beach_tropez": PeripheralEntry("turtle_beach_tropez", "Turtle Beach Tropez", "sound", 1995, 0.006, "RARE", "Dream SAM9407"),
    "ensoniq_soundscape": PeripheralEntry("ensoniq_soundscape", "Ensoniq Soundscape", "sound", 1994, 0.006, "RARE", "OTTO wavetable"),
    "ensoniq_audio_pci": PeripheralEntry("ensoniq_audio_pci", "Ensoniq AudioPCI", "sound", 1997, 0.004, "UNCOMMON", "ES1370"),
    
    # Aureal 3D - 0.006-0.007
    "vortex1": PeripheralEntry("vortex1", "Aureal Vortex AU8820", "sound", 1997, 0.006, "RARE", "A3D 1.0"),
    "vortex2": PeripheralEntry("vortex2", "Aureal Vortex 2 AU8830", "sound", 1998, 0.007, "LEGENDARY", "A3D 2.0"),
    "vortex_advantage": PeripheralEntry("vortex_advantage", "Aureal Vortex Advantage", "sound", 1999, 0.006, "RARE", "Budget A3D"),
    
    # Common 90s cards - 0.002-0.004
    "ess_audiodrive": PeripheralEntry("ess_audiodrive", "ESS AudioDrive", "sound", 1995, 0.003, "UNCOMMON", "ES1688"),
    "opl3sax": PeripheralEntry("opl3sax", "Yamaha OPL3-SAx", "sound", 1995, 0.003, "UNCOMMON", "Integrated"),
    "cs4232": PeripheralEntry("cs4232", "Crystal CS4232", "sound", 1994, 0.003, "UNCOMMON", "Windows Sound System"),
    "sblive": PeripheralEntry("sblive", "Sound Blaster Live!", "sound", 1998, 0.003, "UNCOMMON", "EMU10K1"),
    "sblive_value": PeripheralEntry("sblive_value", "Sound Blaster Live! Value", "sound", 1999, 0.002, "COMMON", "Budget Live"),
    "generic_ac97": PeripheralEntry("generic_ac97", "Generic AC'97 Audio", "sound", 1998, 0.001, "COMMON", "Integrated"),
}

# =============================================================================
# NETWORK CARDS - Tiny bonuses for vintage networking
# =============================================================================
NETWORK_CARD_DATABASE: Dict[str, PeripheralEntry] = {
    # Mythic networking (pre-Ethernet) - max 0.01
    "arcnet_datapoint": PeripheralEntry("arcnet_datapoint", "Datapoint ARCnet", "network", 1977, 0.010, "MYTHIC", "Original ARCnet!"),
    "arcnet_smc": PeripheralEntry("arcnet_smc", "SMC ARCnet PC130", "network", 1985, 0.008, "LEGENDARY", "8-bit ARCnet"),
    "arcnet_avery": PeripheralEntry("arcnet_avery", "Avery ARCnet", "network", 1986, 0.007, "LEGENDARY", "16-bit ARCnet"),
    "token_ring_16_4": PeripheralEntry("token_ring_16_4", "IBM Token Ring 16/4", "network", 1985, 0.009, "LEGENDARY", "MCA Token Ring"),
    "token_ring_isa": PeripheralEntry("token_ring_isa", "IBM Token Ring ISA", "network", 1987, 0.008, "LEGENDARY", "ISA Token Ring"),
    "token_ring_isa2": PeripheralEntry("token_ring_isa2", "IBM Token Ring II ISA", "network", 1989, 0.007, "RARE", "16-bit Token Ring"),
    
    # LocalTalk/AppleTalk - 0.006-0.008
    "localtalk_lc": PeripheralEntry("localtalk_lc", "Apple LocalTalk LC", "network", 1990, 0.007, "LEGENDARY", "PDS LocalTalk"),
    "localtalk_nubus": PeripheralEntry("localtalk_nubus", "Apple LocalTalk NuBus", "network", 1988, 0.007, "LEGENDARY", "NuBus"),
    "farallon_pn": PeripheralEntry("farallon_pn", "Farallon PhoneNET", "network", 1987, 0.007, "LEGENDARY", "LocalTalk over RJ-11"),
    "dayna_etherprint": PeripheralEntry("dayna_etherprint", "Dayna EtherPrint", "network", 1990, 0.006, "RARE", "LocalTalk bridge"),
    
    # Early Ethernet - 0.006-0.008
    "3c501": PeripheralEntry("3c501", "3Com 3C501 EtherLink", "network", 1982, 0.008, "LEGENDARY", "Original EtherLink"),
    "3c503": PeripheralEntry("3c503", "3Com 3C503 EtherLink II", "network", 1985, 0.007, "LEGENDARY", "8-bit NE2000"),
    "ne1000": PeripheralEntry("ne1000", "Novell NE1000", "network", 1987, 0.007, "LEGENDARY", "8-bit NE"),
    "ne2000": PeripheralEntry("ne2000", "Novell NE2000", "network", 1989, 0.006, "RARE", "16-bit NE"),
    "wd8003": PeripheralEntry("wd8003", "Western Digital WD8003", "network", 1986, 0.007, "LEGENDARY", "SMC Elite"),
    "wd8013": PeripheralEntry("wd8013", "Western Digital WD8013", "network", 1988, 0.006, "RARE", "SMC Elite16"),
    
    # Standard 90s Ethernet - 0.002-0.004
    "3c509": PeripheralEntry("3c509", "3Com 3C509 EtherLink III", "network", 1992, 0.004, "UNCOMMON", "ISA 10Base-T"),
    "3c905": PeripheralEntry("3c905", "3Com 3C905 Fast EtherLink", "network", 1996, 0.003, "UNCOMMON", "PCI 100Base-TX"),
    "intel_etherexpress": PeripheralEntry("intel_etherexpress", "Intel EtherExpress", "network", 1991, 0.004, "UNCOMMON", "ISA"),
    "intel_etherexpress_pro": PeripheralEntry("intel_etherexpress_pro", "Intel EtherExpress Pro", "network", 1994, 0.003, "UNCOMMON", "ISA/PCI"),
    "smc_ultrachip": PeripheralEntry("smc_ultrachip", "SMC Ultra", "network", 1992, 0.004, "UNCOMMON", "SMC 83C790"),
    "ne2000_pci": PeripheralEntry("ne2000_pci", "NE2000 PCI Clone", "network", 1995, 0.002, "COMMON", "RTL8029"),
    "rtl8139": PeripheralEntry("rtl8139", "Realtek RTL8139", "network", 1997, 0.002, "COMMON", "Cheap Fast Ethernet"),
    "generic_100mbit": PeripheralEntry("generic_100mbit", "Generic 100Mbit NIC", "network", 1998, 0.001, "COMMON", "Standard"),
}

# =============================================================================
# STORAGE CONTROLLERS - Tiny bonuses for vintage storage
# =============================================================================
STORAGE_CONTROLLER_DATABASE: Dict[str, PeripheralEntry] = {
    # Early SCSI - max 0.01
    "adaptec_aha1540": PeripheralEntry("adaptec_aha1540", "Adaptec AHA-1540", "storage", 1990, 0.009, "LEGENDARY", "ISA SCSI-1"),
    "adaptec_aha1542": PeripheralEntry("adaptec_aha1542", "Adaptec AHA-1542", "storage", 1992, 0.008, "LEGENDARY", "ISA SCSI-2 bus master"),
    "adaptec_aha2940": PeripheralEntry("adaptec_aha2940", "Adaptec AHA-2940", "storage", 1994, 0.006, "RARE", "PCI Fast SCSI"),
    "adaptec_aha2940uw": PeripheralEntry("adaptec_aha2940uw", "Adaptec AHA-2940UW", "storage", 1996, 0.005, "UNCOMMON", "PCI Ultra Wide"),
    "buslogic_bt542": PeripheralEntry("buslogic_bt542", "BusLogic BT-542", "storage", 1991, 0.008, "LEGENDARY", "ISA SCSI"),
    "buslogic_bt946c": PeripheralEntry("buslogic_bt946c", "BusLogic BT-946C", "storage", 1994, 0.006, "RARE", "PCI SCSI"),
    "ncr_53c810": PeripheralEntry("ncr_53c810", "NCR 53C810", "storage", 1993, 0.006, "RARE", "PCI SCSI"),
    "symbios_53c875": PeripheralEntry("symbios_53c875", "Symbios 53C875", "storage", 1995, 0.005, "UNCOMMON", "PCI Ultra SCSI"),
    
    # EISA/MCA RAID - 0.008-0.009
    "dpt_pm2024": PeripheralEntry("dpt_pm2024", "DPT PM2024", "storage", 1992, 0.009, "LEGENDARY", "EISA RAID"),
    "dpt_pm3334uw": PeripheralEntry("dpt_pm3334uw", "DPT PM3334UW", "storage", 1996, 0.007, "RARE", "PCI Ultra Wide RAID"),
    "compaq_smart_array": PeripheralEntry("compaq_smart_array", "Compaq Smart Array", "storage", 1993, 0.008, "LEGENDARY", "EISA RAID"),
    "mylex_acceleraid": PeripheralEntry("mylex_acceleraid", "Mylex AcceleRAID", "storage", 1995, 0.007, "RARE", "PCI RAID"),
    
    # Early IDE - 0.004-0.006
    "promise_dc4030": PeripheralEntry("promise_dc4030", "Promise DC4030", "storage", 1993, 0.006, "RARE", "VLB IDE cache"),
    "cmd640": PeripheralEntry("cmd640", "CMD 640 PCI IDE", "storage", 1994, 0.005, "UNCOMMON", "Early PCI IDE (buggy)"),
    "intel_piix": PeripheralEntry("intel_piix", "Intel PIIX", "storage", 1994, 0.004, "UNCOMMON", "Integrated IDE"),
    "intel_piix3": PeripheralEntry("intel_piix3", "Intel PIIX3", "storage", 1996, 0.003, "COMMON", "Standard IDE"),
    "promise_ultra33": PeripheralEntry("promise_ultra33", "Promise Ultra33", "storage", 1997, 0.003, "UNCOMMON", "ATA-33"),
    "promise_ultra66": PeripheralEntry("promise_ultra66", "Promise Ultra66", "storage", 1999, 0.002, "COMMON", "ATA-66"),
    
    # Standard - 0.001-0.002
    "generic_ide": PeripheralEntry("generic_ide", "Generic IDE Controller", "storage", 1995, 0.001, "COMMON", "Standard"),
    "generic_sata": PeripheralEntry("generic_sata", "Generic SATA Controller", "storage", 2003, 0.001, "COMMON", "Standard"),
}

# =============================================================================
# MODEMS - Tiny bonuses for vintage modems
# =============================================================================
MODEM_DATABASE: Dict[str, PeripheralEntry] = {
    # Legendary modems - max 0.008
    "hayes_smartmodem": PeripheralEntry("hayes_smartmodem", "Hayes Smartmodem 1200", "modem", 1982, 0.008, "MYTHIC", "Original AT commands"),
    "hayes_ultra_96": PeripheralEntry("hayes_ultra_96", "Hayes Ultra 96", "modem", 1989, 0.007, "LEGENDARY", "9600 bps"),
    "hayes_optima": PeripheralEntry("hayes_optima", "Hayes Optima 288", "modem", 1994, 0.005, "RARE", "28.8k V.34"),
    "telebit_trailblazer": PeripheralEntry("telebit_trailblazer", "Telebit TrailBlazer", "modem", 1986, 0.008, "LEGENDARY", "PEP protocol"),
    "telebit_t2500": PeripheralEntry("telebit_t2500", "Telebit T2500", "modem", 1990, 0.007, "LEGENDARY", "V.32bis + PEP"),
    "usr_courier": PeripheralEntry("usr_courier", "USR Courier HST", "modem", 1988, 0.007, "LEGENDARY", "HST protocol"),
    "usr_courier_dual": PeripheralEntry("usr_courier_dual", "USR Courier Dual Standard", "modem", 1992, 0.006, "RARE", "HST + V.32bis"),
    "usr_sportster": PeripheralEntry("usr_sportster", "USR Sportster 14.4", "modem", 1993, 0.004, "UNCOMMON", "Consumer 14.4k"),
    "usr_sportster_288": PeripheralEntry("usr_sportster_288", "USR Sportster 28.8", "modem", 1995, 0.003, "UNCOMMON", "V.34"),
    
    # Standard 90s modems - 0.001-0.003
    "zoom_288": PeripheralEntry("zoom_288", "Zoom 28.8", "modem", 1995, 0.002, "COMMON", "Budget V.34"),
    "generic_336": PeripheralEntry("generic_336", "Generic 33.6 Modem", "modem", 1996, 0.002, "COMMON", "V.34+"),
    "generic_56k": PeripheralEntry("generic_56k", "Generic 56K Modem", "modem", 1998, 0.001, "COMMON", "V.90"),
    "winmodem": PeripheralEntry("winmodem", "Generic Winmodem", "modem", 1997, 0.001, "COMMON", "Software modem"),
}

# =============================================================================
# SPECIALTY CARDS - Video capture, MPEG, Amiga cards, etc.
# =============================================================================
SPECIALTY_DATABASE: Dict[str, PeripheralEntry] = {
    # Video capture - 0.005-0.008
    "video_spigot": PeripheralEntry("video_spigot", "Creative Video Spigot", "capture", 1991, 0.007, "LEGENDARY", "Early video capture"),
    "intel_smart_video": PeripheralEntry("intel_smart_video", "Intel Smart Video Recorder", "capture", 1993, 0.006, "RARE", "Indeo capture"),
    "miro_dc10": PeripheralEntry("miro_dc10", "miro DC10", "capture", 1995, 0.005, "RARE", "Zoran MJPEG"),
    "bt848": PeripheralEntry("bt848", "Brooktree Bt848", "capture", 1996, 0.004, "UNCOMMON", "Common capture chip"),
    
    # MPEG decoders - 0.006-0.008
    "realmagic": PeripheralEntry("realmagic", "RealMagic MPEG", "mpeg", 1993, 0.007, "LEGENDARY", "Hardware MPEG-1"),
    "dvd_express": PeripheralEntry("dvd_express", "Creative DVD Encore", "mpeg", 1998, 0.005, "UNCOMMON", "Hardware MPEG-2"),
    "cinemaster": PeripheralEntry("cinemaster", "Sigma Designs Hollywood+", "mpeg", 1997, 0.005, "UNCOMMON", "DVD decoder"),
    
    # Amiga accelerators - 0.008-0.01
    "blizzard_1230": PeripheralEntry("blizzard_1230", "Blizzard 1230 IV", "amiga_accel", 1995, 0.008, "LEGENDARY", "68030 accelerator"),
    "blizzard_1260": PeripheralEntry("blizzard_1260", "Blizzard 1260", "amiga_accel", 1996, 0.009, "MYTHIC", "68060 accelerator"),
    "cyberstorm_mk2": PeripheralEntry("cyberstorm_mk2", "CyberStorm MK II", "amiga_accel", 1996, 0.009, "MYTHIC", "68060 for A4000"),
    "cyberstorm_ppc": PeripheralEntry("cyberstorm_ppc", "CyberStorm PPC", "amiga_accel", 1997, 0.010, "MYTHIC", "PowerPC for A4000!"),
    "blizzard_ppc": PeripheralEntry("blizzard_ppc", "Blizzard PPC", "amiga_accel", 1997, 0.010, "MYTHIC", "PowerPC for A1200!"),
    
    # Amiga graphics - 0.007-0.009
    "picasso_ii": PeripheralEntry("picasso_ii", "Picasso II", "amiga_gfx", 1993, 0.007, "LEGENDARY", "RTG graphics"),
    "picasso_iv": PeripheralEntry("picasso_iv", "Picasso IV", "amiga_gfx", 1996, 0.008, "LEGENDARY", "Zorro III RTG"),
    "cybervision_64": PeripheralEntry("cybervision_64", "CyberVision 64", "amiga_gfx", 1995, 0.008, "LEGENDARY", "S3 Vision964"),
    "cybervision_3d": PeripheralEntry("cybervision_3d", "CyberVision 64/3D", "amiga_gfx", 1997, 0.008, "LEGENDARY", "S3 ViRGE"),
    
    # Mac accelerators - 0.006-0.008
    "daystar_turbo": PeripheralEntry("daystar_turbo", "DayStar Turbo 040", "mac_accel", 1993, 0.007, "LEGENDARY", "68040 upgrade"),
    "daystar_genesis": PeripheralEntry("daystar_genesis", "DayStar Genesis MP", "mac_accel", 1996, 0.008, "LEGENDARY", "Dual 604e!"),
    "sonnet_crescendo": PeripheralEntry("sonnet_crescendo", "Sonnet Crescendo G3", "mac_accel", 1998, 0.006, "RARE", "G3 upgrade"),
    "newertech_maxpower": PeripheralEntry("newertech_maxpower", "NewerTech MAXpower", "mac_accel", 1997, 0.006, "RARE", "G3 for PCI Macs"),

    # PowerVR / Sega tile-based rendering GPUs - MYTHIC tier
    "powervr_pcx1": PeripheralEntry("powervr_pcx1", "NEC PowerVR PCX1 (Diamond Edge 3D)", "specialty", 1996, 0.010, "MYTHIC", "Tile-based deferred rendering"),
    "powervr_pcx2": PeripheralEntry("powervr_pcx2", "NEC PowerVR PCX2 (Matrox m3D)", "specialty", 1997, 0.009, "MYTHIC", "PowerVR Series 2"),
    "powervr_vf_bundle": PeripheralEntry("powervr_vf_bundle", "Sega Virtua Fighter Bundle Card", "specialty", 1996, 0.010, "MYTHIC", "Rare promo bundle with game port"),
    "videologic_apocalypse": PeripheralEntry("videologic_apocalypse", "VideoLogic Apocalypse 3D", "specialty", 1996, 0.009, "MYTHIC", "UK PowerVR variant"),
    "apocalypse_5d": PeripheralEntry("apocalypse_5d", "VideoLogic Apocalypse 5D", "specialty", 1997, 0.008, "LEGENDARY", "PowerVR + sound"),
}

# =============================================================================
# LOOKUP AND CALCULATION FUNCTIONS
# =============================================================================

ALL_PERIPHERALS = {
    **CDROM_DATABASE,
    **SOUND_CARD_DATABASE,
    **NETWORK_CARD_DATABASE,
    **STORAGE_CONTROLLER_DATABASE,
    **MODEM_DATABASE,
    **SPECIALTY_DATABASE,
}

def get_peripheral(peripheral_id: str) -> Optional[PeripheralEntry]:
    """Look up a peripheral by ID."""
    return ALL_PERIPHERALS.get(peripheral_id.lower())

def calculate_peripheral_bonus(peripherals: List[dict]) -> float:
    """
    Calculate total peripheral bonus from a list of peripherals.
    
    Args:
        peripherals: List of dicts with 'id' and optionally 'category' keys
        
    Returns:
        Total bonus as a float (now 0.001-0.05 range instead of 0.0-1.0)
        
    Note: Bonuses are now MUCH smaller (0.1% to 1% each, max ~5% total)
    to serve as tie-breakers rather than major multiplier influences.
    """
    total_bonus = 0.0
    seen_categories = set()  # Limit one bonus per category
    
    for p in peripherals:
        pid = p.get('id', '').lower()
        entry = get_peripheral(pid)
        
        if entry:
            category = entry.category
            if category not in seen_categories:
                total_bonus += entry.bonus
                seen_categories.add(category)
    
    # Cap total peripheral bonus at 5% (0.05)
    return min(total_bonus, 0.05)

def get_peripheral_stats() -> Dict[str, int]:
    """Get statistics about the peripheral database."""
    stats = {
        'cdrom': len(CDROM_DATABASE),
        'sound': len(SOUND_CARD_DATABASE),
        'network': len(NETWORK_CARD_DATABASE),
        'storage': len(STORAGE_CONTROLLER_DATABASE),
        'modem': len(MODEM_DATABASE),
        'specialty': len(SPECIALTY_DATABASE),
        'total_entries': len(ALL_PERIPHERALS),
    }
    
    # Count by rarity
    rarity_counts = {}
    for entry in ALL_PERIPHERALS.values():
        rarity_counts[entry.rarity] = rarity_counts.get(entry.rarity, 0) + 1
    stats['by_rarity'] = rarity_counts
    
    return stats

def get_highest_bonus_peripherals(limit: int = 20) -> List[dict]:
    """Get the peripherals with highest bonuses."""
    sorted_peripherals = sorted(
        ALL_PERIPHERALS.values(),
        key=lambda x: x.bonus,
        reverse=True
    )
    
    return [
        {
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'bonus': p.bonus,
            'bonus_percent': f"+{p.bonus * 100:.1f}%",
            'rarity': p.rarity,
            'year': p.year
        }
        for p in sorted_peripherals[:limit]
    ]

# =============================================================================
# TEST / DEMO
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("RustChain Peripherals Database v1.1.0 (Rebalanced)")
    print("Peripheral bonuses are now TINY (0.1% - 1% each)")
    print("=" * 60)
    
    stats = get_peripheral_stats()
    print(f"\nTotal Peripherals: {stats['total_entries']}")
    print(f"  CD-ROM:   {stats['cdrom']}")
    print(f"  Sound:    {stats['sound']}")
    print(f"  Network:  {stats['network']}")
    print(f"  Storage:  {stats['storage']}")
    print(f"  Modem:    {stats['modem']}")
    print(f"  Specialty:{stats['specialty']}")
    
    print("\nBy Rarity:")
    for rarity, count in sorted(stats['by_rarity'].items()):
        print(f"  {rarity}: {count}")
    
    print("\n" + "=" * 60)
    print("Top 15 Highest Bonus Peripherals (now much smaller!):")
    print("-" * 60)
    for p in get_highest_bonus_peripherals(15):
        print(f"  {p['name']:35} {p['bonus_percent']:>6}  ({p['rarity']})")
    
    print("\n" + "=" * 60)
    print("Example Bonus Calculation:")
    print("-" * 60)
    test_peripherals = [
        {"id": "gus_classic", "category": "sound"},
        {"id": "mt32", "category": "sound"},  # Same category, won't stack
        {"id": "arcnet_datapoint", "category": "network"},
        {"id": "adaptec_aha1540", "category": "storage"},
    ]
    bonus = calculate_peripheral_bonus(test_peripherals)
    print(f"GUS Classic + ARCnet + AHA-1540 = +{bonus * 100:.2f}%")
    print("(Note: MT-32 doesn't stack with GUS - same category)")
    print("=" * 60)
