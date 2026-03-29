package org.rustchain;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Logger;

/**
 * Miner — RustChain Proof-of-Antiquity mining loop for the JVM.
 *
 * <p>Each cycle:
 * <ol>
 *   <li>Collect a fresh hardware {@link Fingerprint}</li>
 *   <li>POST to {@code /attest/submit} via {@link RustChainClient}</li>
 *   <li>Print the result with ANSI colour coding</li>
 *   <li>Sleep for the configured interval</li>
 * </ol>
 *
 * <h3>CLI usage</h3>
 * <pre>
 * java -jar rustchain-sdk-jar-with-dependencies.jar \
 *      --node-url  https://rustchain.org \
 *      --miner-id  my-miner-001 \
 *      --interval  60
 * </pre>
 *
 * <p>SIGINT (Ctrl-C) triggers a graceful shutdown after the current cycle
 * completes.
 */
public class Miner implements Runnable {

    // ── ANSI colour codes ─────────────────────────────────────────────────────

    private static final String RESET   = "\u001B[0m";
    private static final String BOLD    = "\u001B[1m";
    private static final String RED     = "\u001B[31m";
    private static final String GREEN   = "\u001B[32m";
    private static final String YELLOW  = "\u001B[33m";
    private static final String CYAN    = "\u001B[36m";
    private static final String MAGENTA = "\u001B[35m";
    private static final String DIM     = "\u001B[2m";

    // ── Logger (suppress with -Djava.util.logging.config.file=...) ───────────

    private static final Logger LOG = Logger.getLogger(Miner.class.getName());

    // ── Configuration ─────────────────────────────────────────────────────────

    private final String   nodeUrl;
    private final String   minerId;
    private final int      intervalSeconds;

    // ── State ─────────────────────────────────────────────────────────────────

    private final AtomicBoolean running = new AtomicBoolean(false);
    private       long          cycleCount = 0;
    private       long          successCount = 0;
    private       long          failureCount = 0;

    // ── Constructors ──────────────────────────────────────────────────────────

    /**
     * @param nodeUrl         RustChain node base URL (e.g. {@code "https://rustchain.org"})
     * @param minerId         unique miner identifier string
     * @param intervalSeconds seconds to sleep between attestation cycles
     */
    public Miner(String nodeUrl, String minerId, int intervalSeconds) {
        this.nodeUrl          = nodeUrl;
        this.minerId          = minerId;
        this.intervalSeconds  = Math.max(1, intervalSeconds);
    }

    // ── Entry point ───────────────────────────────────────────────────────────

    /**
     * CLI entry point.  Parse {@code --node-url}, {@code --miner-id},
     * {@code --interval} flags then start the mining loop.
     */
    public static void main(String[] args) {
        String nodeUrl  = "https://rustchain.org";
        String minerId  = "java-miner-" + System.getProperty("user.name", "anon");
        int    interval = 60;

        // ── Argument parsing ─────────────────────────────────────────────────
        for (int i = 0; i < args.length - 1; i++) {
            switch (args[i]) {
                case "--node-url":  nodeUrl  = args[++i]; break;
                case "--miner-id":  minerId  = args[++i]; break;
                case "--interval":
                    try { interval = Integer.parseInt(args[++i]); }
                    catch (NumberFormatException e) {
                        System.err.println(RED + "[ERROR] --interval must be an integer" + RESET);
                        System.exit(1);
                    }
                    break;
                case "--help": case "-h":
                    printHelp();
                    System.exit(0);
                    break;
                default:
                    System.err.println(YELLOW + "[WARN] Unknown argument: " + args[i] + RESET);
            }
        }

        Miner miner = new Miner(nodeUrl, minerId, interval);

        // ── Graceful shutdown on SIGINT ──────────────────────────────────────
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            miner.stop();
            System.out.println();
            System.out.println(YELLOW + BOLD + "⏹  Miner stopped gracefully." + RESET);
            miner.printSummary();
        }));

        miner.run();
    }

    // ── Runnable ──────────────────────────────────────────────────────────────

    @Override
    public void run() {
        running.set(true);
        printBanner();

        RustChainClient client = new RustChainClient(nodeUrl);

        // Verify node reachability before entering the mining loop
        System.out.println(DIM + "  Checking node health …" + RESET);
        RustChainClient.ApiResponse health = client.healthCheck();
        if (!health.isSuccess()) {
            System.out.println(YELLOW + "  [WARN] Health check returned HTTP "
                    + health.getStatusCode() + " — continuing anyway." + RESET);
        } else {
            String version = health.extractField("version");
            System.out.println(GREEN + "  ✔  Node healthy"
                    + (version != null ? " (v" + version + ")" : "")
                    + RESET);
        }

        System.out.println();

        // ── Mining loop ──────────────────────────────────────────────────────
        while (running.get()) {
            cycleCount++;
            String ts = timestamp();

            System.out.println(CYAN + BOLD + "━━━  Cycle #" + cycleCount
                    + "  [" + ts + "]  ━━━" + RESET);

            // 1. Collect fingerprint
            System.out.print(DIM + "  Collecting hardware fingerprint … " + RESET);
            Fingerprint fp = Fingerprint.collect();
            System.out.println(GREEN + "done" + RESET);
            System.out.println(DIM + "  arch=" + fp.getArch()
                    + "  cores=" + fp.getCores()
                    + "  drift=" + fp.getClockDriftNs() + "ns" + RESET);

            // 2. Build attestation payload
            Map<String, Object> payload = buildPayload(fp);

            // 3. Submit attestation
            System.out.print(DIM + "  Submitting attestation … " + RESET);
            long t0   = System.currentTimeMillis();
            RustChainClient.ApiResponse resp = client.submitAttestation(payload);
            long rtt  = System.currentTimeMillis() - t0;

            if (resp.isSuccess()) {
                successCount++;
                System.out.println(GREEN + BOLD + "✔  OK" + RESET
                        + DIM + " (HTTP " + resp.getStatusCode() + ", " + rtt + " ms)" + RESET);
                printResponseHighlight(resp);
            } else {
                failureCount++;
                System.out.println(RED + BOLD + "✘  FAILED" + RESET
                        + DIM + " (HTTP " + resp.getStatusCode() + ", " + rtt + " ms)" + RESET);
                System.out.println(DIM + "  Body: " + truncate(resp.getBody(), 200) + RESET);
            }

            // 4. Sleep
            if (running.get()) {
                System.out.println(DIM + "  Next attestation in " + intervalSeconds + " s …" + RESET);
                System.out.println();
                sleepSeconds(intervalSeconds);
            }
        }
    }

    /** Signal the mining loop to stop after the current cycle completes. */
    public void stop() {
        running.set(false);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /** Build the full attestation payload expected by {@code /attest/submit}. */
    private Map<String, Object> buildPayload(Fingerprint fp) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("miner_id",   minerId);
        payload.put("device",     fp.toDeviceMap());
        payload.put("fingerprint", fp.toFingerprintMap());

        // signals sub-object — MAC addresses are not available from pure Java;
        // we supply an empty list and let the node derive network signals.
        Map<String, Object> signals = new LinkedHashMap<>();
        signals.put("macs", new java.util.ArrayList<>());
        payload.put("signals", signals);

        return payload;
    }

    /** Print a human-readable excerpt of a successful attestation response. */
    private static void printResponseHighlight(RustChainClient.ApiResponse resp) {
        String reward = resp.extractField("reward");
        String epoch  = resp.extractField("epoch");
        String score  = resp.extractField("score");

        if (reward != null) {
            System.out.println(MAGENTA + "  💰 reward=" + reward + RESET);
        }
        if (epoch != null) {
            System.out.println(DIM + "  epoch=" + epoch
                    + (score != null ? "  score=" + score : "")
                    + RESET);
        }
    }

    private static void printBanner() {
        System.out.println();
        System.out.println(CYAN + BOLD
            + "  ██████╗ ██╗   ██╗███████╗████████╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗" + RESET);
        System.out.println(CYAN + BOLD
            + "  ██╔══██╗██║   ██║██╔════╝╚══██╔══╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║" + RESET);
        System.out.println(CYAN + BOLD
            + "  ██████╔╝██║   ██║███████╗   ██║   ██║     ███████║███████║██║██╔██╗ ██║" + RESET);
        System.out.println(CYAN + BOLD
            + "  ██╔══██╗██║   ██║╚════██║   ██║   ██║     ██╔══██║██╔══██║██║██║╚██╗██║" + RESET);
        System.out.println(CYAN + BOLD
            + "  ██║  ██║╚██████╔╝███████║   ██║   ╚██████╗██║  ██║██║  ██║██║██║ ╚████║" + RESET);
        System.out.println(CYAN + BOLD
            + "  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝" + RESET);
        System.out.println();
        System.out.println(BOLD + "  RustChain Java Miner  —  Proof-of-Antiquity" + RESET);
        System.out.println(DIM  + "  Old hardware outearns new hardware." + RESET);
        System.out.println();
    }

    private static void printHelp() {
        System.out.println("Usage: java -jar rustchain-sdk-jar-with-dependencies.jar [options]");
        System.out.println();
        System.out.println("Options:");
        System.out.println("  --node-url  <url>   RustChain node URL  (default: https://rustchain.org)");
        System.out.println("  --miner-id  <id>    Miner identifier    (default: java-miner-<user>)");
        System.out.println("  --interval  <secs>  Attestation interval in seconds (default: 60)");
        System.out.println("  --help              Show this message");
        System.out.println();
        System.out.println("Examples:");
        System.out.println("  java -jar rustchain-sdk.jar --miner-id my-g4-powerbook --interval 30");
        System.out.println("  java -jar rustchain-sdk.jar --node-url http://localhost:5000");
    }

    private void printSummary() {
        System.out.println();
        System.out.println(BOLD + "  Summary" + RESET);
        System.out.println(DIM + "  ─────────────────────────────" + RESET);
        System.out.println("  Cycles    : " + cycleCount);
        System.out.println(GREEN + "  Successes : " + successCount + RESET);
        System.out.println((failureCount > 0 ? RED : DIM) + "  Failures  : " + failureCount + RESET);
        System.out.println();
    }

    private static String timestamp() {
        return DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
                .withZone(ZoneOffset.UTC)
                .format(Instant.now())
                + " UTC";
    }

    private static String truncate(String s, int maxLen) {
        if (s == null) return "";
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "…";
    }

    private static void sleepSeconds(int seconds) {
        try {
            Thread.sleep((long) seconds * 1000L);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
