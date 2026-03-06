// Example demonstrating full agent lifecycle management.
// Run with: go run examples/agent_management.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/Scottcjn/Rustchain/sdk/go/agenteco"
)

func main() {
	// Create client with API key for write operations
	// In production, load this from environment variables
	apiKey := "" // Set your API key here or use NewClientWithDefaults() for read-only

	var client *agenteco.Client
	var err error

	if apiKey != "" {
		client, err = agenteco.NewClientWithKey(apiKey)
	} else {
		client, err = agenteco.NewClientWithDefaults()
		log.Println("Running in read-only mode (no API key)")
	}
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// === CREATE AGENT ===
	fmt.Println("=== Creating Agent ===")

	createReq := &agenteco.CreateAgentRequest{
		Name:        fmt.Sprintf("DataProcessor-%d", time.Now().Unix()),
		Description: "High-performance data processing agent for batch operations",
		Type:        agenteco.AgentTypeCompute,
		Metadata: map[string]interface{}{
			"version":           "1.0.0",
			"capabilities":      []string{"transform", "validate", "aggregate"},
			"max_batch_size":    10000,
			"supported_formats": []string{"JSON", "CSV", "Parquet"},
		},
	}

	agent, err := client.CreateAgent(ctx, createReq)
	if err != nil {
		log.Printf("Failed to create agent: %v", err)
		// For demo, try to get an existing agent
		agents, _, listErr := client.ListAgents(ctx, &agenteco.ListOptions{Limit: 1})
		if listErr != nil || len(agents) == 0 {
			log.Fatal("No agents available for demo")
		}
		agent = &agents[0]
		fmt.Printf("Using existing agent: %s\n", agent.Name)
	} else {
		fmt.Printf("Created agent: %s (ID: %s)\n", agent.Name, agent.AgentID)
		fmt.Printf("  Type: %s\n", agent.Type)
		fmt.Printf("  Status: %s\n", agent.Status)
		fmt.Printf("  Reputation: %d\n", agent.Reputation)
	}

	// === GET AGENT ===
	fmt.Println("\n=== Getting Agent Details ===")

	fetchedAgent, err := client.GetAgent(ctx, agent.AgentID)
	if err != nil {
		log.Printf("Failed to get agent: %v", err)
	} else {
		fmt.Printf("Agent: %s\n", fetchedAgent.Name)
		fmt.Printf("  Owner: %s\n", fetchedAgent.Owner)
		fmt.Printf("  Description: %s\n", fetchedAgent.Description)
		fmt.Printf("  Active Tasks: %d\n", fetchedAgent.ActiveTasks)
		fmt.Printf("  Completed Tasks: %d\n", fetchedAgent.CompletedTasks)
		fmt.Printf("  Total Earnings: %.2f RTC\n", fetchedAgent.TotalEarnings)
		fmt.Printf("  Created: %s\n", fetchedAgent.CreatedAt.Format(time.RFC3339))
		fmt.Printf("  Last Active: %s\n", fetchedAgent.LastActiveAt.Format(time.RFC3339))
	}

	// === UPDATE AGENT ===
	fmt.Println("\n=== Updating Agent ===")

	updateReq := &agenteco.UpdateAgentRequest{
		Description: "Updated: High-performance data processing with ML capabilities",
		Metadata: map[string]interface{}{
			"version":    "1.1.0",
			"ml_enabled": true,
		},
	}

	updatedAgent, err := client.UpdateAgent(ctx, agent.AgentID, updateReq)
	if err != nil {
		log.Printf("Failed to update agent: %v", err)
	} else {
		fmt.Printf("Updated agent description: %s\n", updatedAgent.Description)
		fmt.Printf("Updated metadata version: %v\n", updatedAgent.Metadata["version"])
	}

	// === GET AGENT METRICS ===
	fmt.Println("\n=== Getting Agent Metrics ===")

	periodStart := time.Now().Add(-24 * time.Hour)
	periodEnd := time.Now()

	metrics, err := client.GetAgentMetrics(ctx, agent.AgentID, periodStart, periodEnd)
	if err != nil {
		log.Printf("Failed to get metrics: %v", err)
	} else {
		fmt.Printf("Metrics for %s:\n", metrics.AgentID)
		fmt.Printf("  Uptime: %.2f%%\n", metrics.Uptime)
		fmt.Printf("  Success Rate: %.2f%%\n", metrics.SuccessRate)
		fmt.Printf("  Avg Response Time: %.2f ms\n", metrics.AverageResponseTime)
		fmt.Printf("  Tasks Completed: %d\n", metrics.TasksCompleted)
		fmt.Printf("  Tasks Failed: %d\n", metrics.TasksFailed)
		fmt.Printf("  Period Earnings: %.2f RTC\n", metrics.TotalEarnings)
	}

	// === GET AGENT REWARDS ===
	fmt.Println("\n=== Getting Agent Rewards ===")

	rewardsOpts := &agenteco.ListOptions{
		Page:  1,
		Limit: 5,
	}

	rewards, meta, err := client.GetAgentRewards(ctx, agent.AgentID, rewardsOpts)
	if err != nil {
		log.Printf("Failed to get rewards: %v", err)
	} else {
		fmt.Printf("Rewards (Page %d of %d):\n", meta.CurrentPage, meta.TotalPages)
		for i, reward := range rewards {
			fmt.Printf("  %d. %.2f RTC - %s (%s)\n",
				i+1, reward.Amount, reward.Type, reward.Status)
			if reward.Description != "" {
				fmt.Printf("     %s\n", reward.Description)
			}
		}
	}

	// === GET AGENT ECONOMY STATS ===
	fmt.Println("\n=== Getting Agent Economy Stats ===")

	agentStats, err := client.GetAgentEconomyStats(ctx, agent.AgentID)
	if err != nil {
		log.Printf("Failed to get agent stats: %v", err)
	} else {
		fmt.Printf("Agent-specific stats:\n")
		fmt.Printf("  Active Tasks: %d\n", agentStats.PendingTasks)
		fmt.Printf("  Completed Tasks: %d\n", agentStats.CompletedTasks)
	}

	// === LIST AGENTS WITH FILTERS ===
	fmt.Println("\n=== Listing Agents by Type ===")

	filterOpts := &agenteco.ListOptions{
		Page:      1,
		Limit:     10,
		SortBy:    "reputation",
		SortOrder: "desc",
		Filter: map[string]string{
			"type": string(agenteco.AgentTypeCompute),
		},
	}

	computeAgents, meta, err := client.ListAgents(ctx, filterOpts)
	if err != nil {
		log.Printf("Failed to list compute agents: %v", err)
	} else {
		fmt.Printf("Compute Agents (Page %d of %d):\n", meta.CurrentPage, meta.TotalPages)
		for i, a := range computeAgents {
			fmt.Printf("  %d. %s - Reputation: %d, Earnings: %.2f RTC\n",
				i+1, a.Name, a.Reputation, a.TotalEarnings)
		}
	}

	// === DELETE AGENT (if created) ===
	if apiKey != "" && agent.Name[:13] == "DataProcessor" {
		fmt.Println("\n=== Deleting Test Agent ===")

		err = client.DeleteAgent(ctx, agent.AgentID)
		if err != nil {
			log.Printf("Failed to delete agent: %v", err)
		} else {
			fmt.Printf("Successfully deleted agent: %s\n", agent.Name)
		}
	}

	fmt.Println("\n=== Agent Management Complete ===")
}
