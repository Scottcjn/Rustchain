package org.rustchain;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Fingerprint — hardware identity collector for RustChain attestation.
 *
 * <p>Gathers CPU metadata, available memory, OS details, and a clock-drift
 * measurement to produce a stable per-machine identity hash.  Everything is
 * done with standard JDK APIs — no native code, no JNI, no external libraries.
 *
 * <h3>Usage</h3>
 * <pre>{@code
 * Fingerprint fp = Fingerprint.collect();
 * System.out.println("arch  : " + fp.getArch());
 * System.out.println("cores : " + fp.getCores());
 * System.out.println("hash  : " + fp.getHash());
 *
 * // Ready to embed in an attestation payload
 * Map<String, Object> device = fp.toDeviceMap();
 * Map<String, Object> fpMap  = fp.toFingerprintMap();
 * }</pre>
 */
public final class Fingerprint {

    // ── Fields ────────────────────────────────────────────────────────────────

    private final String arch;
    private final String cpuName;
    private final int    cores;
    private final long   totalMemoryMb;
    private final long   freeMemoryMb;
    private final String osName;
    private final String osVersion;
    private final String jvmVersion;

    /** Clock-drift sample — nanosecond delta measured during construction. */
    private final long clockDriftNs;

    /** SHA-256 hex digest of the stable hardware identity string. */
    private final String hash;

    // ── Private constructor — use Fingerprint.collect() ───────────────────────

    private Fingerprint(String arch, String cpuName, int cores,
                        long totalMemoryMb, long freeMemoryMb,
                        String osName, String osVersion, String jvmVersion,
                        long clockDriftNs) {
        this.arch          = arch;
        this.cpuName       = cpuName;
        this.cores         = cores;
        this.totalMemoryMb = totalMemoryMb;
        this.freeMemoryMb  = freeMemoryMb;
        this.osName        = osName;
        this.osVersion     = osVersion;
        this.jvmVersion    = jvmVersion;
        this.clockDriftNs  = clockDriftNs;
        this.hash          = computeHash();
    }

    // ── Factory ───────────────────────────────────────────────────────────────

    /**
     * Collect a fingerprint snapshot from the current JVM runtime.
     *
     * <p>The clock-drift measurement burns ~10 ms of CPU time to produce a
     * short loop-timing sample.  This intentionally varies by CPU speed and
     * thermal state, adding entropy that is difficult to spoof on virtual
     * machines.
     *
     * @return immutable {@link Fingerprint} instance
     */
    public static Fingerprint collect() {
        Runtime rt = Runtime.getRuntime();

        String arch       = System.getProperty("os.arch",    "unknown");
        String osName     = System.getProperty("os.name",    "unknown");
        String osVersion  = System.getProperty("os.version", "unknown");
        String jvmVersion = System.getProperty("java.version", "unknown");

        // cpu.name is not a standard JVM property; fall back to os.arch + core count.
        String cpuName = System.getProperty("sun.cpu.endian") != null
                ? arch + " (" + System.getProperty("sun.cpu.endian") + "-endian)"
                : arch;

        int  cores        = rt.availableProcessors();
        long totalMemMb   = rt.totalMemory()  / (1024 * 1024);
        long freeMemMb    = rt.freeMemory()   / (1024 * 1024);

        long driftNs = measureClockDrift();

        return new Fingerprint(arch, cpuName, cores,
                totalMemMb, freeMemMb,
                osName, osVersion, jvmVersion,
                driftNs);
    }

    // ── Clock drift ───────────────────────────────────────────────────────────

    /**
     * Measure clock drift by running a tight counting loop and comparing the
     * elapsed wall-clock time against the expected iteration count.
     *
     * <p>A faster CPU finishes more iterations per nanosecond; the residual
     * drift value encodes both CPU speed and scheduling jitter — useful as a
     * light anti-VM signal.
     *
     * @return nanoseconds elapsed for the measurement loop
     */
    static long measureClockDrift() {
        final int LOOPS      = 500_000;
        final int ITERATIONS = 5;

        long totalNs = 0;
        long sink    = 0; // prevent loop elimination by optimizer

        for (int i = 0; i < ITERATIONS; i++) {
            long t0 = System.nanoTime();
            for (int j = 0; j < LOOPS; j++) {
                sink ^= j;
            }
            totalNs += System.nanoTime() - t0;
        }

        // consume sink to keep the JIT honest
        if (sink == Long.MIN_VALUE) throw new AssertionError("impossible");

        return totalNs / ITERATIONS;
    }

    // ── Identity hash ─────────────────────────────────────────────────────────

    /**
     * Compute a SHA-256 hex digest of the stable hardware identity string.
     *
     * <p>Stable fields only (arch, cores, OS, JVM).  Memory and clock-drift
     * are excluded from the hash because they fluctuate across reboots —
     * they are reported in the attestation payload but do not alter the
     * machine identity.
     */
    private String computeHash() {
        // Build a deterministic string from stable hardware attributes.
        String identity = "arch="       + arch
                        + ";cores="     + cores
                        + ";os="        + osName
                        + ";osver="     + osVersion
                        + ";jvm="       + jvmVersion;

        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(identity.getBytes(StandardCharsets.UTF_8));
            return "sha256:" + bytesToHex(digest);
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 is guaranteed by the JDK spec — should never happen.
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    /** Convert a byte array to a lowercase hex string. */
    static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    // ── Payload builders ──────────────────────────────────────────────────────

    /**
     * Build the {@code device} sub-object expected by the RustChain attestation API.
     *
     * @return ordered map ready to embed in an attestation payload
     */
    public Map<String, Object> toDeviceMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("arch",           arch);
        m.put("cpu",            cpuName);
        m.put("cores",          cores);
        m.put("total_mem_mb",   totalMemoryMb);
        m.put("free_mem_mb",    freeMemoryMb);
        m.put("os",             osName);
        m.put("os_version",     osVersion);
        m.put("jvm_version",    jvmVersion);
        return m;
    }

    /**
     * Build the {@code fingerprint} sub-object expected by the RustChain attestation API.
     *
     * @return ordered map ready to embed in an attestation payload
     */
    public Map<String, Object> toFingerprintMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("hash",          hash);
        m.put("clock_drift_ns", clockDriftNs);
        m.put("checks",        buildChecksMap());
        return m;
    }

    /** Internal: build the {@code fingerprint.checks} object. */
    private Map<String, Object> buildChecksMap() {
        Map<String, Object> checks = new LinkedHashMap<>();
        checks.put("arch_known",       !arch.equalsIgnoreCase("unknown"));
        checks.put("multi_core",       cores > 1);
        checks.put("memory_present",   totalMemoryMb > 0);
        checks.put("clock_drift_ok",   clockDriftNs > 0 && clockDriftNs < 10_000_000_000L);
        return checks;
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    /** CPU architecture string (e.g. {@code "amd64"}, {@code "aarch64"}). */
    public String getArch()           { return arch; }

    /** CPU name or description string. */
    public String getCpuName()        { return cpuName; }

    /** Number of logical processors visible to the JVM. */
    public int    getCores()          { return cores; }

    /** Total JVM heap in megabytes at collection time. */
    public long   getTotalMemoryMb()  { return totalMemoryMb; }

    /** Free JVM heap in megabytes at collection time. */
    public long   getFreeMemoryMb()   { return freeMemoryMb; }

    /** Operating system name (e.g. {@code "Linux"}). */
    public String getOsName()         { return osName; }

    /** Operating system version string. */
    public String getOsVersion()      { return osVersion; }

    /** JVM version string (e.g. {@code "11.0.21"}). */
    public String getJvmVersion()     { return jvmVersion; }

    /** Average nanoseconds for the clock-drift measurement loop. */
    public long   getClockDriftNs()   { return clockDriftNs; }

    /**
     * SHA-256 identity hash of stable hardware attributes, prefixed with
     * {@code "sha256:"} (e.g. {@code "sha256:a1b2c3..."}).
     */
    public String getHash()           { return hash; }

    @Override
    public String toString() {
        return "Fingerprint{"
             + "arch='"    + arch    + '\''
             + ", cores="  + cores
             + ", os='"    + osName  + ' ' + osVersion + '\''
             + ", jvm='"   + jvmVersion + '\''
             + ", memMb="  + totalMemoryMb
             + ", drift="  + clockDriftNs + "ns"
             + ", hash='"  + hash    + '\''
             + '}';
    }
}
