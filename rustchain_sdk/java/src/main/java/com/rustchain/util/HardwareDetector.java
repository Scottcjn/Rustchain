package com.rustchain.util;

import com.rustchain.model.HardwareFingerprint;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.management.ManagementFactory;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Detects hardware information for the Proof of Antiquity system.
 * Gathers CPU, memory, storage, BIOS, and OS information.
 */
public class HardwareDetector {

    private static final Logger logger = LoggerFactory.getLogger(HardwareDetector.class);

    /**
     * Detect all hardware information.
     *
     * @return HardwareFingerprint containing detected hardware info
     */
    public HardwareFingerprint detect() {
        HardwareFingerprint fingerprint = new HardwareFingerprint();

        fingerprint.setCpu(detectCPU());
        fingerprint.setMemory(detectMemory());
        fingerprint.setOs(detectOS());
        fingerprint.setBios(detectBIOS());
        fingerprint.setMotherboard(detectMotherboard());
        fingerprint.setStorage(detectStorage());

        logger.info("Hardware detection complete: CPU={}, OS={}, Era={}",
                fingerprint.getCpu().getModel(),
                fingerprint.getOs().getName(),
                fingerprint.getCpu().getEra());

        return fingerprint;
    }

    /**
     * Detect CPU information.
     */
    public HardwareFingerprint.CPUInfo detectCPU() {
        HardwareFingerprint.CPUInfo cpuInfo = new HardwareFingerprint.CPUInfo();

        String osName = System.getProperty("os.name").toLowerCase();
        String arch = System.getProperty("os.arch");
        int cores = Runtime.getRuntime().availableProcessors();

        cpuInfo.setThreads(cores);
        cpuInfo.setCores(cores); // Simplified - assumes no HT

        if (osName.contains("win")) {
            detectCPUWindows(cpuInfo);
        } else if (osName.contains("mac")) {
            detectCPUMac(cpuInfo);
        } else if (osName.contains("nix") || osName.contains("nux") || osName.contains("aix")) {
            detectCPULinux(cpuInfo);
        } else {
            detectCPUFallback(cpuInfo, arch);
        }

        // Calculate vintage score based on CPU era
        calculateCPUVintageScore(cpuInfo);

        return cpuInfo;
    }

    private void detectCPUWindows(HardwareFingerprint.CPUInfo cpuInfo) {
        try {
            Process process = Runtime.getRuntime().exec("wmic cpu get Name,Manufacturer,MaxClockSpeed /format:csv");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.contains(",")) {
                        String[] parts = line.split(",");
                        if (parts.length >= 4) {
                            cpuInfo.setVendor(parts[2].trim());
                            cpuInfo.setModel(parts[3].trim());
                        }
                    }
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Windows CPU detection failed, using fallback", e);
            detectCPUFallback(cpuInfo, System.getProperty("os.arch"));
        }
    }

    private void detectCPUMac(HardwareFingerprint.CPUInfo cpuInfo) {
        try {
            Process process = Runtime.getRuntime().exec("sysctl -n machdep.cpu.brand_string");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String model = reader.readLine();
                if (model != null) {
                    cpuInfo.setModel(model.trim());
                    cpuInfo.setVendor(detectCPUVendor(model));
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Mac CPU detection failed, using fallback", e);
            detectCPUFallback(cpuInfo, System.getProperty("os.arch"));
        }
    }

    private void detectCPULinux(HardwareFingerprint.CPUInfo cpuInfo) {
        try {
            Process process = Runtime.getRuntime().exec("cat /proc/cpuinfo");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.startsWith("model name")) {
                        String model = line.split(":")[1].trim();
                        cpuInfo.setModel(model);
                        cpuInfo.setVendor(detectCPUVendor(model));
                        break;
                    }
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Linux CPU detection failed, using fallback", e);
            detectCPUFallback(cpuInfo, System.getProperty("os.arch"));
        }
    }

    private void detectCPUFallback(HardwareFingerprint.CPUInfo cpuInfo, String arch) {
        cpuInfo.setVendor("Unknown");
        cpuInfo.setModel(arch);
        cpuInfo.setFamily(arch);
    }

    private String detectCPUVendor(String model) {
        if (model == null) return "Unknown";
        String lower = model.toLowerCase();
        if (lower.contains("intel")) return "Intel";
        if (lower.contains("amd")) return "AMD";
        if (lower.contains("apple")) return "Apple";
        if (lower.contains("ibm")) return "IBM";
        if (lower.contains("motorola")) return "Motorola";
        return "Unknown";
    }

    /**
     * Detect memory information.
     */
    public HardwareFingerprint.MemoryInfo detectMemory() {
        HardwareFingerprint.MemoryInfo memoryInfo = new HardwareFingerprint.MemoryInfo();

        long totalMemory = Runtime.getRuntime().totalMemory() / (1024 * 1024);
        long maxMemory = Runtime.getRuntime().maxMemory() / (1024 * 1024);

        memoryInfo.setTotalMB(maxMemory);
        memoryInfo.setType(detectMemoryType());
        memoryInfo.setChannels(1); // Simplified

        return memoryInfo;
    }

    private String detectMemoryType() {
        // Simplified detection - in production would use platform-specific tools
        long totalMem = Runtime.getRuntime().maxMemory() / (1024 * 1024);
        if (totalMem < 512) return "SDRAM";
        if (totalMem < 2048) return "DDR";
        if (totalMem < 8192) return "DDR2";
        if (totalMem < 32768) return "DDR3";
        return "DDR4+";
    }

    /**
     * Detect OS information.
     */
    public HardwareFingerprint.OSInfo detectOS() {
        HardwareFingerprint.OSInfo osInfo = new HardwareFingerprint.OSInfo();

        osInfo.setName(System.getProperty("os.name"));
        osInfo.setVersion(System.getProperty("os.version"));
        osInfo.setArchitecture(System.getProperty("os.arch"));

        // Calculate vintage bonus for vintage OS
        calculateOSVintageBonus(osInfo);

        return osInfo;
    }

    /**
     * Detect BIOS information.
     */
    public HardwareFingerprint.BIOSInfo detectBIOS() {
        HardwareFingerprint.BIOSInfo biosInfo = new HardwareFingerprint.BIOSInfo();

        String osName = System.getProperty("os.name").toLowerCase();

        if (osName.contains("win")) {
            detectBIOSWindows(biosInfo);
        } else if (osName.contains("mac")) {
            detectBIOSMac(biosInfo);
        } else if (osName.contains("nix") || osName.contains("nux")) {
            detectBIOSLinux(biosInfo);
        } else {
            biosInfo.setVendor("Unknown");
            biosInfo.setVersion("Unknown");
            biosInfo.setDate("Unknown");
        }

        calculateBIOSVintageBonus(biosInfo);

        return biosInfo;
    }

    private void detectBIOSWindows(HardwareFingerprint.BIOSInfo biosInfo) {
        try {
            Process process = Runtime.getRuntime().exec("wmic bios get Manufacturer,ReleaseDate,Version /format:csv");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.contains(",")) {
                        String[] parts = line.split(",");
                        if (parts.length >= 4) {
                            biosInfo.setVendor(parts[2].trim());
                            biosInfo.setVersion(parts[3].trim());
                            biosInfo.setDate(parts[2].trim()); // Simplified
                        }
                    }
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Windows BIOS detection failed", e);
        }
    }

    private void detectBIOSMac(HardwareFingerprint.BIOSInfo biosInfo) {
        biosInfo.setVendor("Apple");
        biosInfo.setVersion("EFI");
        try {
            Process process = Runtime.getRuntime().exec("ioreg -l | grep IOPlatformBuildVersion");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line = reader.readLine();
                if (line != null) {
                    biosInfo.setVersion(line.split("=")[1].trim());
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Mac BIOS detection failed", e);
        }
    }

    private void detectBIOSLinux(HardwareFingerprint.BIOSInfo biosInfo) {
        try {
            Process process = Runtime.getRuntime().exec("dmidecode -s bios-version");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String version = reader.readLine();
                if (version != null) {
                    biosInfo.setVersion(version.trim());
                }
            }
            process.waitFor();

            process = Runtime.getRuntime().exec("dmidecode -s bios-date");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String date = reader.readLine();
                if (date != null) {
                    biosInfo.setDate(date.trim());
                }
            }
            process.waitFor();

            process = Runtime.getRuntime().exec("dmidecode -s bios-vendor");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String vendor = reader.readLine();
                if (vendor != null) {
                    biosInfo.setVendor(vendor.trim());
                }
            }
            process.waitFor();
        } catch (Exception e) {
            logger.debug("Linux BIOS detection failed (may need root)", e);
        }
    }

    /**
     * Detect motherboard information.
     */
    public HardwareFingerprint.MotherboardInfo detectMotherboard() {
        HardwareFingerprint.MotherboardInfo moboInfo = new HardwareFingerprint.MotherboardInfo();

        String osName = System.getProperty("os.name").toLowerCase();

        if (osName.contains("win")) {
            try {
                Process process = Runtime.getRuntime().exec("wmic baseboard get Manufacturer,Product,SerialNumber /format:csv");
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (line.contains(",")) {
                            String[] parts = line.split(",");
                            if (parts.length >= 4) {
                                moboInfo.setManufacturer(parts[2].trim());
                                moboInfo.setModel(parts[3].trim());
                                moboInfo.setSerial(parts[4].trim());
                            }
                        }
                    }
                }
                process.waitFor();
            } catch (Exception e) {
                logger.debug("Windows motherboard detection failed", e);
            }
        } else if (osName.contains("nix") || osName.contains("nux")) {
            try {
                Process process = Runtime.getRuntime().exec("dmidecode -s baseboard-product-name");
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                    String model = reader.readLine();
                    if (model != null) moboInfo.setModel(model.trim());
                }
                process.waitFor();

                process = Runtime.getRuntime().exec("dmidecode -s baseboard-manufacturer");
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                    String manufacturer = reader.readLine();
                    if (manufacturer != null) moboInfo.setManufacturer(manufacturer.trim());
                }
                process.waitFor();
            } catch (Exception e) {
                logger.debug("Linux motherboard detection failed (may need root)", e);
            }
        }

        if (moboInfo.getManufacturer() == null) {
            moboInfo.setManufacturer("Unknown");
            moboInfo.setModel("Unknown");
        }

        return moboInfo;
    }

    /**
     * Detect storage information.
     */
    public HardwareFingerprint.StorageInfo detectStorage() {
        HardwareFingerprint.StorageInfo storageInfo = new HardwareFingerprint.StorageInfo();

        // Get total storage capacity
        File[] roots = File.listRoots();
        long totalCapacity = 0;
        for (File root : roots) {
            totalCapacity += root.getTotalSpace();
        }
        storageInfo.setCapacityGB(totalCapacity / (1024 * 1024 * 1024));

        // Detect storage type (simplified)
        storageInfo.setType(detectStorageType());
        storageInfo.setModel("Generic");

        return storageInfo;
    }

    private String detectStorageType() {
        // Simplified detection based on available space and performance
        File testFile = new File(System.getProperty("java.io.tmpdir"));
        long freeSpace = testFile.getFreeSpace();

        if (freeSpace < 10L * 1024 * 1024 * 1024) {
            return "HDD";
        } else if (freeSpace < 100L * 1024 * 1024 * 1024) {
            return "HDD/SSD";
        } else {
            return "SSD";
        }
    }

    /**
     * Calculate vintage score for CPU based on model and features.
     */
    private void calculateCPUVintageScore(HardwareFingerprint.CPUInfo cpuInfo) {
        String model = cpuInfo.getModel().toLowerCase();
        int score = 100; // Base score
        String era = "Modern";

        // Detect CPU era and assign vintage score
        if (model.contains("pentium") || model.contains("486") || model.contains("386")) {
            era = "Classic (1990s)";
            score = 500;
        } else if (model.contains("core 2") || model.contains("core2")) {
            era = "Core 2 Era (2006-2008)";
            score = 350;
        } else if (model.contains("i7") || model.contains("i5") || model.contains("i3")) {
            // Check generation
            Pattern pattern = Pattern.compile("i[357]\\s?(\\d)\\d{3}");
            Matcher matcher = pattern.matcher(model);
            if (matcher.find()) {
                int gen = Integer.parseInt(matcher.group(1));
                if (gen <= 3) {
                    era = "Early Core i (2008-2012)";
                    score = 250;
                } else if (gen <= 7) {
                    era = "Mid Core i (2012-2017)";
                    score = 150;
                } else {
                    era = "Modern Core i (2017+)";
                    score = 100;
                }
            }
        } else if (model.contains("ryzen")) {
            era = "Ryzen Era (2017+)";
            score = 100;
        } else if (model.contains("athlon")) {
            era = "Athlon Era (1999-2005)";
            score = 400;
        } else if (model.contains("xeon")) {
            era = "Xeon Server";
            score = 200;
        }

        cpuInfo.setVintageScore(score);
        cpuInfo.setEra(era);
    }

    /**
     * Calculate vintage bonus for OS.
     */
    private void calculateOSVintageBonus(HardwareFingerprint.OSInfo osInfo) {
        String name = osInfo.getName().toLowerCase();
        int bonus = 0;

        if (name.contains("windows")) {
            if (name.contains("95") || name.contains("98")) {
                bonus = 300;
            } else if (name.contains("xp")) {
                bonus = 250;
            } else if (name.contains("7")) {
                bonus = 150;
            } else if (name.contains("10")) {
                bonus = 50;
            }
        } else if (name.contains("mac os")) {
            if (name.contains("x") || name.contains("10")) {
                bonus = 100;
            }
        } else if (name.contains("linux")) {
            bonus = 50;
        }

        osInfo.setVintageBonus(bonus);
    }

    /**
     * Calculate vintage bonus for BIOS.
     */
    private void calculateBIOSVintageBonus(HardwareFingerprint.BIOSInfo biosInfo) {
        String date = biosInfo.getDate();
        int bonus = 0;

        if (date != null && !date.equals("Unknown")) {
            try {
                // Parse BIOS date (format: MM/DD/YYYY or YYYYMMDD)
                int year = extractYear(date);
                if (year > 0) {
                    if (year <= 1995) {
                        bonus = 300;
                    } else if (year <= 2000) {
                        bonus = 250;
                    } else if (year <= 2005) {
                        bonus = 200;
                    } else if (year <= 2010) {
                        bonus = 150;
                    } else if (year <= 2015) {
                        bonus = 100;
                    }
                }
            } catch (Exception e) {
                logger.debug("Could not parse BIOS date", e);
            }
        }

        biosInfo.setVintageBonus(bonus);
    }

    private int extractYear(String date) {
        // Try various date formats
        Pattern pattern = Pattern.compile("(19|20)\\d{2}");
        Matcher matcher = pattern.matcher(date);
        if (matcher.find()) {
            return Integer.parseInt(matcher.group());
        }
        return -1;
    }
}
