package com.rustchain.cli;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.RuntimeMXBean;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * Node Health Monitor for RustChain.
 * Monitors system resources and node status.
 */
public class NodeHealthMonitor {

    private static final Logger logger = LoggerFactory.getLogger(NodeHealthMonitor.class);

    private final String nodeName;
    private final String rpcUrl;
    private Instant startTime;

    public NodeHealthMonitor(String nodeName, String rpcUrl) {
        this.nodeName = nodeName;
        this.rpcUrl = rpcUrl;
        this.startTime = Instant.now();
    }

    /**
     * Run the health monitor.
     */
    public void run() {
        System.out.println("RustChain Node Health Monitor");
        System.out.println("=".repeat(60));
        System.out.println("Node: " + nodeName);
        System.out.println("RPC URL: " + rpcUrl);
        System.out.println();

        while (true) {
            try {
                checkHealth();
                Thread.sleep(30000); // Check every 30 seconds
            } catch (InterruptedException e) {
                logger.info("Monitor interrupted");
                break;
            } catch (Exception e) {
                logger.error("Health check failed", e);
            }
        }
    }

    /**
     * Perform a single health check.
     */
    public HealthReport checkHealth() {
        HealthReport report = new HealthReport();
        report.setTimestamp(Instant.now());
        report.setNodeName(nodeName);
        report.setUptime(Duration.between(startTime, Instant.now()));

        // Check system resources
        report.setMemoryUsage(getMemoryUsage());
        report.setCpuUsage(getCpuUsage());

        // Check node RPC
        report.setNodeHealthy(checkNodeRpc());

        // Determine overall status
        report.setStatus(determineStatus(report));

        // Log report
        logReport(report);

        return report;
    }

    private void logReport(HealthReport report) {
        System.out.println();
        System.out.println("[" + report.getTimestamp() + "] Health Check");
        System.out.println("  Status: " + report.getStatus());
        System.out.println("  Memory: " + report.getMemoryUsage() + "%");
        System.out.println("  CPU: " + report.getCpuUsage() + "%");
        System.out.println("  Node RPC: " + (report.isNodeHealthy() ? "OK" : "DOWN"));
        System.out.println("  Uptime: " + formatDuration(report.getUptime()));
    }

    private String formatDuration(Duration duration) {
        long hours = duration.toHours();
        long minutes = duration.toMinutes() % 60;
        long seconds = duration.getSeconds() % 60;
        return String.format("%dh %dm %ds", hours, minutes, seconds);
    }

    private int getMemoryUsage() {
        MemoryMXBean memoryBean = ManagementFactory.getMemoryMXBean();
        long used = memoryBean.getHeapMemoryUsage().getUsed();
        long max = memoryBean.getHeapMemoryUsage().getMax();
        if (max <= 0) return 0;
        return (int) (used * 100 / max);
    }

    private int getCpuUsage() {
        // Simplified - in production would use OS-specific tools
        return -1; // Not available via standard Java
    }

    private boolean checkNodeRpc() {
        if (rpcUrl == null || rpcUrl.isEmpty()) {
            return true; // Skip if no RPC configured
        }

        try {
            URL url = new URL(rpcUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            conn.setRequestMethod("GET");
            
            int responseCode = conn.getResponseCode();
            conn.disconnect();
            
            return responseCode >= 200 && responseCode < 400;
        } catch (IOException e) {
            logger.debug("RPC check failed", e);
            return false;
        }
    }

    private String determineStatus(HealthReport report) {
        if (!report.isNodeHealthy()) {
            return "CRITICAL";
        }
        if (report.getMemoryUsage() > 90) {
            return "WARNING";
        }
        return "HEALTHY";
    }

    /**
     * Health report data class.
     */
    public static class HealthReport {
        private Instant timestamp;
        private String nodeName;
        private Duration uptime;
        private int memoryUsage;
        private int cpuUsage;
        private boolean nodeHealthy;
        private String status;

        public Instant getTimestamp() {
            return timestamp;
        }

        public void setTimestamp(Instant timestamp) {
            this.timestamp = timestamp;
        }

        public String getNodeName() {
            return nodeName;
        }

        public void setNodeName(String nodeName) {
            this.nodeName = nodeName;
        }

        public Duration getUptime() {
            return uptime;
        }

        public void setUptime(Duration uptime) {
            this.uptime = uptime;
        }

        public int getMemoryUsage() {
            return memoryUsage;
        }

        public void setMemoryUsage(int memoryUsage) {
            this.memoryUsage = memoryUsage;
        }

        public int getCpuUsage() {
            return cpuUsage;
        }

        public void setCpuUsage(int cpuUsage) {
            this.cpuUsage = cpuUsage;
        }

        public boolean isNodeHealthy() {
            return nodeHealthy;
        }

        public void setNodeHealthy(boolean nodeHealthy) {
            this.nodeHealthy = nodeHealthy;
        }

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }
    }

    /**
     * CLI entry point for the health monitor.
     */
    public static void main(String[] args) {
        String nodeName = "default-node";
        String rpcUrl = "";

        // Parse arguments
        for (int i = 0; i < args.length; i++) {
            if ("--name".equals(args[i]) && i + 1 < args.length) {
                nodeName = args[++i];
            } else if ("--rpc".equals(args[i]) && i + 1 < args.length) {
                rpcUrl = args[++i];
            } else if ("--help".equals(args[i])) {
                System.out.println("RustChain Node Health Monitor");
                System.out.println();
                System.out.println("Usage: java -cp rustchain.jar com.rustchain.cli.NodeHealthMonitor [options]");
                System.out.println();
                System.out.println("Options:");
                System.out.println("  --name <name>    Node name (default: default-node)");
                System.out.println("  --rpc <url>      Node RPC URL for health checks");
                System.out.println("  --help           Show this help message");
                return;
            }
        }

        NodeHealthMonitor monitor = new NodeHealthMonitor(nodeName, rpcUrl);
        
        // Add shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println();
            System.out.println("Shutting down health monitor...");
        }));

        monitor.run();
    }
}
