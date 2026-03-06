package com.rustchain.agent;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.fasterxml.jackson.databind.*;

/**
 * RustChain Agent Economy Java SDK
 * 
 * Java client library for the RustChain Agent Economy marketplace.
 * Supports job posting, browsing, claiming, delivery, and reputation queries.
 */
public class RustChainAgentClient {
    private final String baseUrl;
    private final ObjectMapper mapper;
    
    public RustChainAgentClient(String baseUrl) {
        this.baseUrl = baseUrl;
        this.mapper = new ObjectMapper();
    }
    
    /**
     * Get marketplace statistics
     */
    public MarketStats getMarketStats() throws Exception {
        String response = get("/agent/stats");
        return mapper.readValue(response, MarketStats.class);
    }
    
    /**
     * Browse open jobs
     */
    public List<Job> getJobs(String category, int limit) throws Exception {
        StringBuilder url = new StringBuilder("/agent/jobs?limit=").append(limit);
        if (category != null && !category.isEmpty()) {
            url.append("&category=").append(URLEncoder.encode(category, "UTF-8"));
        }
        String response = get(url.toString());
        return Arrays.asList(mapper.readValue(response, Job[].class));
    }
    
    /**
     * Get job details
     */
    public Job getJob(String jobId) throws Exception {
        String response = get("/agent/jobs/" + jobId);
        return mapper.readValue(response, Job.class);
    }
    
    /**
     * Post a new job
     */
    public Job postJob(String posterWallet, String title, String description, 
                      String category, double rewardRtc, List<String> tags) throws Exception {
        Map<String, Object> payload = new HashMap<>();
        payload.put("poster_wallet", posterWallet);
        payload.put("title", title);
        payload.put("description", description);
        payload.put("category", category);
        payload.put("reward_rtc", rewardRtc);
        if (tags != null) {
            payload.put("tags", tags);
        }
        
        String response = post("/agent/jobs", mapper.writeValueAsString(payload));
        return mapper.readValue(response, Job.class);
    }
    
    /**
     * Claim a job
     */
    public Map<String, Object> claimJob(String jobId, String workerWallet) throws Exception {
        Map<String, Object> payload = new HashMap<>();
        payload.put("worker_wallet", workerWallet);
        
        String response = post("/agent/jobs/" + jobId + "/claim", mapper.writeValueAsString(payload));
        return mapper.readValue(response, Map.class);
    }
    
    /**
     * Submit delivery
     */
    public Map<String, Object> deliverJob(String jobId, String workerWallet, 
                                         String deliverableUrl, String resultSummary) throws Exception {
        Map<String, Object> payload = new HashMap<>();
        payload.put("worker_wallet", workerWallet);
        payload.put("deliverable_url", deliverableUrl);
        payload.put("result_summary", resultSummary);
        
        String response = post("/agent/jobs/" + jobId + "/deliver", mapper.writeValueAsString(payload));
        return mapper.readValue(response, Map.class);
    }
    
    /**
     * Accept delivery and release escrow
     */
    public Map<String, Object> acceptDelivery(String jobId, String posterWallet) throws Exception {
        Map<String, Object> payload = new HashMap<>();
        payload.put("poster_wallet", posterWallet);
        
        String response = post("/agent/jobs/" + jobId + "/accept", mapper.writeValueAsString(payload));
        return mapper.readValue(response, Map.class);
    }
    
    /**
     * Get agent reputation
     */
    public Reputation getReputation(String wallet) throws Exception {
        String response = get("/agent/reputation/" + wallet);
        return mapper.readValue(response, Reputation.class);
    }
    
    // HTTP helpers
    private String get(String path) throws Exception {
        URL url = new URL(baseUrl + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setRequestProperty("Content-Type", "application/json");
        
        return readResponse(conn);
    }
    
    private String post(String path, String body) throws Exception {
        URL url = new URL(baseUrl + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setDoOutput(true);
        
        try (OutputStream os = conn.getOutputStream()) {
            byte[] input = body.getBytes(StandardCharsets.UTF_8);
            os.write(input, 0, input.length);
        }
        
        return readResponse(conn);
    }
    
    private String readResponse(HttpURLConnection conn) throws Exception {
        int responseCode = conn.getResponseCode();
        BufferedReader br = new BufferedReader(
            new InputStreamReader(
                responseCode >= 200 && responseCode < 300 ? conn.getInputStream() : conn.getErrorStream(),
                StandardCharsets.UTF_8
            )
        );
        
        StringBuilder response = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            response.append(line);
        }
        br.close();
        
        if (responseCode >= 400) {
            throw new RuntimeException("HTTP " + responseCode + ": " + response.toString());
        }
        
        return response.toString();
    }
    
    // Data classes
    public static class MarketStats {
        public int total_jobs;
        public int open_jobs;
        public int completed_jobs;
        public double total_rtc_locked;
        public double average_reward;
        public List<CategoryCount> top_categories;
        
        public static class CategoryCount {
            public String category;
            public int count;
        }
    }
    
    public static class Job {
        public String id;
        public String poster_wallet;
        public String title;
        public String description;
        public String category;
        public double reward_rtc;
        public List<String> tags;
        public String status;
        public String created_at;
    }
    
    public static class Reputation {
        public String wallet;
        public int trust_score;
        public String trust_level;
        public double avg_rating;
        public int total_jobs;
        public int completed_jobs;
        public int disputed_jobs;
    }
    
    public static void main(String[] args) throws Exception {
        RustChainAgentClient client = new RustChainAgentClient("https://rustchain.org");
        
        // Example: Get market stats
        MarketStats stats = client.getMarketStats();
        System.out.println("Total Jobs: " + stats.total_jobs);
        System.out.println("Open Jobs: " + stats.open_jobs);
        System.out.println("Completed: " + stats.completed_jobs);
        
        // Example: Browse jobs
        List<Job> jobs = client.getJobs(null, 5);
        System.out.println("\nOpen Jobs:");
        for (Job job : jobs) {
            System.out.println("- " + job.title + " (" + job.reward_rtc + " RTC)");
        }
    }
}
