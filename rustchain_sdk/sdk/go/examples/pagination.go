// Example demonstrating pagination patterns.
// Run with: go run examples/pagination.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/Scottcjn/Rustchain/sdk/go/agenteco"
)

func main() {
	client, err := agenteco.NewClientWithDefaults()
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	// === MANUAL PAGINATION ===
	fmt.Println("=== Manual Pagination ===")

	opts := &agenteco.ListOptions{
		Page:      1,
		Limit:     10,
		SortBy:    "created_at",
		SortOrder: "desc",
	}

	totalAgents := 0
	pageCount := 0

	for {
		agents, meta, err := client.ListAgents(ctx, opts)
		if err != nil {
			log.Printf("Failed to list agents: %v", err)
			break
		}

		pageCount++
		totalAgents += len(agents)

		fmt.Printf("Page %d: Retrieved %d agents (Total so far: %d)\n",
			meta.CurrentPage, len(agents), totalAgents)

		if !meta.HasNext {
			fmt.Printf("Completed: %d pages, %d total agents\n", pageCount, totalAgents)
			break
		}

		opts.Page++

		// Small delay to avoid rate limiting
		time.Sleep(50 * time.Millisecond)
	}

	// === PAGINATION WITH PROGRESS ===
	fmt.Println("\n=== Pagination with Progress ===")

	opts = &agenteco.ListOptions{
		Page:  1,
		Limit: 20,
	}

	tasks, meta, err := client.ListTasks(ctx, opts)
	if err != nil {
		log.Printf("Failed to get initial tasks: %v", err)
	} else {
		totalTasks := meta.TotalItems
		processed := len(tasks)

		fmt.Printf("Processing %d tasks...\n", totalTasks)
		fmt.Printf("Progress: %d/%d (%.1f%%)\n",
			processed, totalTasks, float64(processed)*100/float64(totalTasks))

		for opts.Page < meta.TotalPages {
			opts.Page++
			tasks, _, err := client.ListTasks(ctx, opts)
			if err != nil {
				log.Printf("Failed to list page %d: %v", opts.Page, err)
				break
			}

			processed += len(tasks)
			progress := float64(processed) * 100 / float64(totalTasks)

			fmt.Printf("Progress: %d/%d (%.1f%%)\n", processed, totalTasks, progress)

			time.Sleep(50 * time.Millisecond)
		}
	}

	// === USING FOREACH ITERATOR ===
	fmt.Println("\n=== Using ForEach Iterator ===")

	agentCount := 0
	err = client.ForEach(ctx, "/agents", &agenteco.ListOptions{Limit: 10}, func(item interface{}) error {
		agent, ok := item.(map[string]interface{})
		if !ok {
			return nil
		}

		agentCount++
		name, _ := agent["name"].(string)
		agentType, _ := agent["type"].(string)

		fmt.Printf("  %d. %s (%s)\n", agentCount, name, agentType)
		return nil
	})

	if err != nil {
		log.Printf("Iterator error: %v", err)
	}
	fmt.Printf("Total agents processed: %d\n", agentCount)

	// === CUSTOM ITERATOR ===
	fmt.Println("\n=== Custom Iterator Pattern ===")

	it := agenteco.NewIterator(client, "/rewards", &agenteco.ListOptions{Limit: 5})

	rewardCount := 0

	for it.Next(ctx) {
		rewardCount++
		// Note: In real usage, you'd type assert to agenteco.Reward
		// This is simplified for the example
	}

	if err := it.Err(); err != nil {
		log.Printf("Iterator error: %v", err)
	}
	fmt.Printf("Total rewards iterated: %d\n", rewardCount)

	// === PAGINATION WITH FILTERS ===
	fmt.Println("\n=== Filtered Pagination ===")

	filterConfigs := []struct {
		name   string
		filter map[string]string
	}{
		{"Active Agents", map[string]string{"status": "active"}},
		{"Idle Agents", map[string]string{"status": "idle"}},
		{"Compute Agents", map[string]string{"type": "compute"}},
		{"Validator Agents", map[string]string{"type": "validator"}},
	}

	for _, config := range filterConfigs {
		opts := &agenteco.ListOptions{
			Page:   1,
			Limit:  5,
			Filter: config.filter,
		}

		_, meta, err := client.ListAgents(ctx, opts)
		if err != nil {
			continue
		}

		fmt.Printf("%s: %d total\n", config.name, meta.TotalItems)
	}

	// === SORTED PAGINATION ===
	fmt.Println("\n=== Sorted Pagination ===")

	sortConfigs := []struct {
		name   string
		sortBy string
		order  string
	}{
		{"By Reputation (High-Low)", "reputation", "desc"},
		{"By Reputation (Low-High)", "reputation", "asc"},
		{"By Earnings (High-Low)", "total_earnings", "desc"},
		{"By Tasks Completed", "completed_tasks", "desc"},
	}

	for _, config := range sortConfigs {
		opts := &agenteco.ListOptions{
			Page:      1,
			Limit:     3,
			SortBy:    config.sortBy,
			SortOrder: config.order,
		}

		agents, _, err := client.ListAgents(ctx, opts)
		if err != nil {
			continue
		}

		fmt.Printf("%s:\n", config.name)
		for i, agent := range agents {
			fmt.Printf("  %d. %s\n", i+1, agent.Name)
		}
	}

	// === LARGE DATASET HANDLING ===
	fmt.Println("\n=== Large Dataset Handling ===")

	// Process in batches
	batchSize := 50
	batchNum := 0
	totalProcessed := 0

	opts = &agenteco.ListOptions{
		Page:  1,
		Limit: batchSize,
	}

	for {
		agents, meta, err := client.ListAgents(ctx, opts)
		if err != nil {
			log.Printf("Batch %d failed: %v", batchNum, err)
			break
		}

		batchNum++
		totalProcessed += len(agents)

		fmt.Printf("Batch %d: Processed %d agents (Total: %d)\n",
			batchNum, len(agents), totalProcessed)

		// Process batch here
		// ...

		if !meta.HasNext {
			break
		}

		opts.Page++
		time.Sleep(100 * time.Millisecond)
	}

	fmt.Printf("Completed: %d batches, %d total agents\n", batchNum, totalProcessed)

	fmt.Println("\n=== Pagination Examples Complete ===")
}
