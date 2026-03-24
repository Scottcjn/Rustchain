// Example basic usage of the RustChain Agent Economy SDK.
// Run with: go run examples/basic_usage.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/Scottcjn/Rustchain/sdk/go/agenteco"
)

func main() {
	// Create a new client with default configuration
	client, err := agenteco.NewClientWithDefaults()
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	// Create a context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Check API health
	fmt.Println("=== Health Check ===")
	health, err := client.Health(ctx)
	if err != nil {
		log.Printf("Health check failed: %v", err)
	} else {
		fmt.Printf("Status: %s\n", health.Status)
		fmt.Printf("Version: %s\n", health.Version)
		fmt.Printf("Uptime: %d seconds\n", health.Uptime)
	}

	// Get economy statistics
	fmt.Println("\n=== Economy Statistics ===")
	stats, err := client.GetEconomyStats(ctx)
	if err != nil {
		log.Printf("Failed to get stats: %v", err)
	} else {
		fmt.Printf("Total Agents: %d\n", stats.TotalAgents)
		fmt.Printf("Active Agents: %d\n", stats.ActiveAgents)
		fmt.Printf("Total Tasks: %d\n", stats.TotalTasks)
		fmt.Printf("Completed Tasks: %d\n", stats.CompletedTasks)
		fmt.Printf("Total Volume: %.2f RTC\n", stats.TotalVolume)
		fmt.Printf("Total Rewards: %.2f RTC\n", stats.TotalRewards)
	}

	// List agents with pagination
	fmt.Println("\n=== Listing Agents ===")
	opts := &agenteco.ListOptions{
		Page:      1,
		Limit:     10,
		SortBy:    "created_at",
		SortOrder: "desc",
	}

	agents, meta, err := client.ListAgents(ctx, opts)
	if err != nil {
		log.Printf("Failed to list agents: %v", err)
	} else {
		fmt.Printf("Page %d of %d (Total: %d agents)\n",
			meta.CurrentPage, meta.TotalPages, meta.TotalItems)

		for i, agent := range agents {
			fmt.Printf("%d. %s (%s) - Status: %s, Reputation: %d\n",
				i+1, agent.Name, agent.Type, agent.Status, agent.Reputation)
		}
	}

	// List tasks
	fmt.Println("\n=== Listing Tasks ===")
	tasks, meta, err := client.ListTasks(ctx, opts)
	if err != nil {
		log.Printf("Failed to list tasks: %v", err)
	} else {
		fmt.Printf("Page %d of %d (Total: %d tasks)\n",
			meta.CurrentPage, meta.TotalPages, meta.TotalItems)

		for i, task := range tasks {
			statusIcon := "⏳"
			switch task.Status {
			case agenteco.TaskStatusCompleted:
				statusIcon = "✅"
			case agenteco.TaskStatusFailed:
				statusIcon = "❌"
			case agenteco.TaskStatusInProgress:
				statusIcon = "🔄"
			}
			fmt.Printf("%d. %s %s - Reward: %.2f RTC\n",
				i+1, statusIcon, task.Title, task.Reward)
		}
	}

	// List rewards
	fmt.Println("\n=== Listing Recent Rewards ===")
	rewards, meta, err := client.ListRewards(ctx, opts)
	if err != nil {
		log.Printf("Failed to list rewards: %v", err)
	} else {
		fmt.Printf("Page %d of %d (Total: %d rewards)\n",
			meta.CurrentPage, meta.TotalPages, meta.TotalItems)

		for i, reward := range rewards {
			fmt.Printf("%d. %.2f RTC (%s) - %s\n",
				i+1, reward.Amount, reward.Type, reward.Status)
		}
	}

	fmt.Println("\n=== Basic Usage Complete ===")
}
