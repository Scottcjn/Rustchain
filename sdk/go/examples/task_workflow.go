// Example demonstrating task creation and management workflow.
// Run with: go run examples/task_workflow.go
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

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// === CREATE TASK ===
	fmt.Println("=== Creating Task ===")

	taskReq := &agenteco.CreateTaskRequest{
		Title:       fmt.Sprintf("Data Validation Task %d", time.Now().Unix()),
		Description: "Validate and clean incoming data stream from sensor network",
		Type:        agenteco.TaskTypeValidation,
		Priority:    8,
		Reward:      15.5,
		Deadline:    time.Now().Add(24 * time.Hour),
		Metadata: map[string]interface{}{
			"data_source":      "sensor_network_01",
			"expected_records": 50000,
			"validation_rules": []string{"null_check", "range_check", "format_check"},
		},
	}

	task, err := client.CreateTask(ctx, taskReq)
	if err != nil {
		log.Printf("Failed to create task: %v", err)
		// For demo, get an existing task
		tasks, _, listErr := client.ListTasks(ctx, &agenteco.ListOptions{Limit: 1})
		if listErr != nil || len(tasks) == 0 {
			log.Fatal("No tasks available for demo")
		}
		task = &tasks[0]
		fmt.Printf("Using existing task: %s\n", task.Title)
	} else {
		fmt.Printf("Created task: %s (ID: %s)\n", task.Title, task.TaskID)
		fmt.Printf("  Type: %s\n", task.Type)
		fmt.Printf("  Priority: %d\n", task.Priority)
		fmt.Printf("  Reward: %.2f RTC\n", task.Reward)
		fmt.Printf("  Deadline: %s\n", task.Deadline.Format(time.RFC3339))
		fmt.Printf("  Status: %s\n", task.Status)
	}

	// === GET TASK ===
	fmt.Println("\n=== Getting Task Details ===")

	fetchedTask, err := client.GetTask(ctx, task.TaskID)
	if err != nil {
		log.Printf("Failed to get task: %v", err)
	} else {
		fmt.Printf("Task: %s\n", fetchedTask.Title)
		fmt.Printf("  Description: %s\n", fetchedTask.Description)
		fmt.Printf("  Requester: %s\n", fetchedTask.Requester)
		fmt.Printf("  Agent: %s\n", fetchedTask.AgentID)
		fmt.Printf("  Status: %s\n", fetchedTask.Status)
		if fetchedTask.StartedAt != nil {
			fmt.Printf("  Started: %s\n", fetchedTask.StartedAt.Format(time.RFC3339))
		}
	}

	// === ASSIGN TASK TO AGENT ===
	fmt.Println("\n=== Assigning Task to Agent ===")

	// First, find an available agent
	agents, _, err := client.ListAgents(ctx, &agenteco.ListOptions{
		Limit: 1,
		Filter: map[string]string{
			"status": string(agenteco.AgentStatusIdle),
		},
	})

	var agentID string
	if err != nil || len(agents) == 0 {
		// Fallback to any active agent
		agents, _, _ = client.ListAgents(ctx, &agenteco.ListOptions{
			Limit: 1,
			Filter: map[string]string{
				"status": string(agenteco.AgentStatusActive),
			},
		})
	}

	if len(agents) > 0 {
		agentID = agents[0].AgentID
		fmt.Printf("Found agent: %s\n", agentID)

		assignedTask, err := client.AssignTask(ctx, task.TaskID, agentID)
		if err != nil {
			log.Printf("Failed to assign task: %v", err)
		} else {
			fmt.Printf("Task assigned to agent: %s\n", assignedTask.AgentID)
			fmt.Printf("New status: %s\n", assignedTask.Status)
			task = assignedTask
		}
	} else {
		fmt.Println("No available agents found, skipping assignment")
	}

	// === UPDATE TASK STATUS ===
	fmt.Println("\n=== Updating Task Status ===")

	// Simulate task progress
	statusUpdates := []agenteco.TaskStatus{
		agenteco.TaskStatusInProgress,
		agenteco.TaskStatusCompleted,
	}

	for _, status := range statusUpdates {
		statusReq := &agenteco.UpdateTaskStatusRequest{
			Status: status,
		}

		if status == agenteco.TaskStatusCompleted {
			statusReq.Result = map[string]interface{}{
				"validated_records":  49850,
				"rejected_records":   150,
				"validation_rate":    0.997,
				"processing_time_ms": 2340,
			}
		}

		updatedTask, err := client.UpdateTaskStatus(ctx, task.TaskID, statusReq)
		if err != nil {
			log.Printf("Failed to update status to %s: %v", status, err)
			break
		}

		fmt.Printf("Task status updated to: %s\n", updatedTask.Status)
		task = updatedTask

		time.Sleep(100 * time.Millisecond) // Small delay between updates
	}

	// === GET TASK RESULT ===
	fmt.Println("\n=== Getting Task Result ===")

	if task.Status == agenteco.TaskStatusCompleted {
		result, err := client.GetTaskResult(ctx, task.TaskID)
		if err != nil {
			log.Printf("Failed to get result: %v", err)
		} else {
			fmt.Printf("Task Result:\n")
			if resultMap, ok := result.(map[string]interface{}); ok {
				for k, v := range resultMap {
					fmt.Printf("  %s: %v\n", k, v)
				}
			} else {
				fmt.Printf("  %v\n", result)
			}
		}
	}

	// === LIST TASKS BY STATUS ===
	fmt.Println("\n=== Listing Tasks by Status ===")

	statuses := []agenteco.TaskStatus{
		agenteco.TaskStatusPending,
		agenteco.TaskStatusInProgress,
		agenteco.TaskStatusCompleted,
	}

	for _, status := range statuses {
		opts := &agenteco.ListOptions{
			Limit: 5,
			Filter: map[string]string{
				"status": string(status),
			},
		}

		tasks, meta, err := client.ListTasks(ctx, opts)
		if err != nil {
			log.Printf("Failed to list %s tasks: %v", status, err)
			continue
		}

		fmt.Printf("%s Tasks (Page %d, Total: %d):\n", status, meta.CurrentPage, meta.TotalItems)
		for i, t := range tasks {
			fmt.Printf("  %d. %s - Reward: %.2f RTC\n", i+1, t.Title, t.Reward)
		}
	}

	// === CANCEL A PENDING TASK ===
	fmt.Println("\n=== Cancelling Task (if pending) ===")

	if task.Status == agenteco.TaskStatusPending || task.Status == agenteco.TaskStatusAssigned {
		cancelledTask, err := client.CancelTask(ctx, task.TaskID)
		if err != nil {
			log.Printf("Failed to cancel task: %v", err)
		} else {
			fmt.Printf("Task cancelled. New status: %s\n", cancelledTask.Status)
		}
	} else {
		fmt.Printf("Task status is %s, cannot cancel\n", task.Status)
	}

	// === CREATE MULTIPLE TASKS ===
	fmt.Println("\n=== Creating Multiple Tasks ===")

	taskTypes := []struct {
		taskType agenteco.TaskType
		title    string
		reward   float64
	}{
		{agenteco.TaskTypeComputation, "Matrix Multiplication", 25.0},
		{agenteco.TaskTypeDataFetch, "Price Feed Update", 5.0},
		{agenteco.TaskTypeStorage, "Data Backup", 10.0},
		{agenteco.TaskTypeCustom, "Custom Processing", 20.0},
	}

	for _, t := range taskTypes {
		req := &agenteco.CreateTaskRequest{
			Title:       fmt.Sprintf("%s %d", t.title, time.Now().UnixNano()%10000),
			Description: fmt.Sprintf("Automated %s task", t.title),
			Type:        t.taskType,
			Priority:    5,
			Reward:      t.reward,
			Deadline:    time.Now().Add(12 * time.Hour),
		}

		createdTask, err := client.CreateTask(ctx, req)
		if err != nil {
			log.Printf("Failed to create %s task: %v", t.taskType, err)
		} else {
			fmt.Printf("Created: %s (ID: %s, Reward: %.2f RTC)\n",
				createdTask.Title, createdTask.TaskID, createdTask.Reward)
		}
	}

	fmt.Println("\n=== Task Workflow Complete ===")
}
