package com.rustchain.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Hardware fingerprint containing CPU, motherboard, and system information.
 * Used to identify and score vintage hardware.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class HardwareFingerprint {

    @JsonProperty("cpu")
    private CPUInfo cpu;

    @JsonProperty("motherboard")
    private MotherboardInfo motherboard;

    @JsonProperty("memory")
    private MemoryInfo memory;

    @JsonProperty("storage")
    private StorageInfo storage;

    @JsonProperty("bios")
    private BIOSInfo bios;

    @JsonProperty("os")
    private OSInfo os;

    public HardwareFingerprint() {
    }

    // Getters and Setters
    public CPUInfo getCpu() {
        return cpu;
    }

    public void setCpu(CPUInfo cpu) {
        this.cpu = cpu;
    }

    public MotherboardInfo getMotherboard() {
        return motherboard;
    }

    public void setMotherboard(MotherboardInfo motherboard) {
        this.motherboard = motherboard;
    }

    public MemoryInfo getMemory() {
        return memory;
    }

    public void setMemory(MemoryInfo memory) {
        this.memory = memory;
    }

    public StorageInfo getStorage() {
        return storage;
    }

    public void setStorage(StorageInfo storage) {
        this.storage = storage;
    }

    public BIOSInfo getBios() {
        return bios;
    }

    public void setBios(BIOSInfo bios) {
        this.bios = bios;
    }

    public OSInfo getOs() {
        return os;
    }

    public void setOs(OSInfo os) {
        this.os = os;
    }

    /**
     * CPU Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class CPUInfo {
        @JsonProperty("vendor")
        private String vendor;

        @JsonProperty("model")
        private String model;

        @JsonProperty("family")
        private String family;

        @JsonProperty("stepping")
        private String stepping;

        @JsonProperty("cores")
        private int cores;

        @JsonProperty("threads")
        private int threads;

        @JsonProperty("base_frequency_mhz")
        private double baseFrequencyMhz;

        @JsonProperty("vintage_score")
        private int vintageScore;

        @JsonProperty("era")
        private String era;

        public CPUInfo() {
        }

        // Getters and Setters
        public String getVendor() {
            return vendor;
        }

        public void setVendor(String vendor) {
            this.vendor = vendor;
        }

        public String getModel() {
            return model;
        }

        public void setModel(String model) {
            this.model = model;
        }

        public String getFamily() {
            return family;
        }

        public void setFamily(String family) {
            this.family = family;
        }

        public String getStepping() {
            return stepping;
        }

        public void setStepping(String stepping) {
            this.stepping = stepping;
        }

        public int getCores() {
            return cores;
        }

        public void setCores(int cores) {
            this.cores = cores;
        }

        public int getThreads() {
            return threads;
        }

        public void setThreads(int threads) {
            this.threads = threads;
        }

        public double getBaseFrequencyMhz() {
            return baseFrequencyMhz;
        }

        public void setBaseFrequencyMhz(double baseFrequencyMhz) {
            this.baseFrequencyMhz = baseFrequencyMhz;
        }

        public int getVintageScore() {
            return vintageScore;
        }

        public void setVintageScore(int vintageScore) {
            this.vintageScore = vintageScore;
        }

        public String getEra() {
            return era;
        }

        public void setEra(String era) {
            this.era = era;
        }
    }

    /**
     * Motherboard Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class MotherboardInfo {
        @JsonProperty("manufacturer")
        private String manufacturer;

        @JsonProperty("model")
        private String model;

        @JsonProperty("chipset")
        private String chipset;

        @JsonProperty("serial")
        private String serial;

        public MotherboardInfo() {
        }

        // Getters and Setters
        public String getManufacturer() {
            return manufacturer;
        }

        public void setManufacturer(String manufacturer) {
            this.manufacturer = manufacturer;
        }

        public String getModel() {
            return model;
        }

        public void setModel(String model) {
            this.model = model;
        }

        public String getChipset() {
            return chipset;
        }

        public void setChipset(String chipset) {
            this.chipset = chipset;
        }

        public String getSerial() {
            return serial;
        }

        public void setSerial(String serial) {
            this.serial = serial;
        }
    }

    /**
     * Memory Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class MemoryInfo {
        @JsonProperty("total_mb")
        private long totalMB;

        @JsonProperty("type")
        private String type;

        @JsonProperty("channels")
        private int channels;

        public MemoryInfo() {
        }

        // Getters and Setters
        public long getTotalMB() {
            return totalMB;
        }

        public void setTotalMB(long totalMB) {
            this.totalMB = totalMB;
        }

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public int getChannels() {
            return channels;
        }

        public void setChannels(int channels) {
            this.channels = channels;
        }
    }

    /**
     * Storage Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class StorageInfo {
        @JsonProperty("type")
        private String type;

        @JsonProperty("capacity_gb")
        private long capacityGB;

        @JsonProperty("model")
        private String model;

        public StorageInfo() {
        }

        // Getters and Setters
        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public long getCapacityGB() {
            return capacityGB;
        }

        public void setCapacityGB(long capacityGB) {
            this.capacityGB = capacityGB;
        }

        public String getModel() {
            return model;
        }

        public void setModel(String model) {
            this.model = model;
        }
    }

    /**
     * BIOS Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class BIOSInfo {
        @JsonProperty("vendor")
        private String vendor;

        @JsonProperty("version")
        private String version;

        @JsonProperty("date")
        private String date;

        @JsonProperty("vintage_bonus")
        private int vintageBonus;

        public BIOSInfo() {
        }

        // Getters and Setters
        public String getVendor() {
            return vendor;
        }

        public void setVendor(String vendor) {
            this.vendor = vendor;
        }

        public String getVersion() {
            return version;
        }

        public void setVersion(String version) {
            this.version = version;
        }

        public String getDate() {
            return date;
        }

        public void setDate(String date) {
            this.date = date;
        }

        public int getVintageBonus() {
            return vintageBonus;
        }

        public void setVintageBonus(int vintageBonus) {
            this.vintageBonus = vintageBonus;
        }
    }

    /**
     * Operating System Information
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class OSInfo {
        @JsonProperty("name")
        private String name;

        @JsonProperty("version")
        private String version;

        @JsonProperty("architecture")
        private String architecture;

        @JsonProperty("vintage_bonus")
        private int vintageBonus;

        public OSInfo() {
        }

        // Getters and Setters
        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getVersion() {
            return version;
        }

        public void setVersion(String version) {
            this.version = version;
        }

        public String getArchitecture() {
            return architecture;
        }

        public void setArchitecture(String architecture) {
            this.architecture = architecture;
        }

        public int getVintageBonus() {
            return vintageBonus;
        }

        public void setVintageBonus(int vintageBonus) {
            this.vintageBonus = vintageBonus;
        }
    }
}
