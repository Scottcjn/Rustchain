// Example demonstrating error handling patterns.
// Run with: go run examples/error_handling.go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
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

	fmt.Println("=== Error Handling Examples ===\n")

	// === NOT FOUND ERROR ===
	fmt.Println("1. Handling Not Found Error")
	_, err = client.GetAgent(ctx, "non-existent-agent-id")
	if err != nil {
		handleError(err)
	}

	// === INVALID INPUT ERROR ===
	fmt.Println("\n2. Handling Invalid Input Error")
	_, err = client.GetAgent(ctx, "")
	if err != nil {
		handleError(err)
	}

	// === API ERROR WITH DETAILS ===
	fmt.Println("\n3. API Error with Details")
	_, err = client.CreateAgent(ctx, &agenteco.CreateAgentRequest{
		Name: "", // Missing required field
	})
	if err != nil {
		handleError(err)
	}

	// === CHECKING ERROR TYPES ===
	fmt.Println("\n4. Checking Error Types")

	// Simulate various error scenarios
	testErrors := []struct {
		name string
		fn   func() error
	}{
		{"Not Found", func() error {
			_, err := client.GetAgent(ctx, "invalid")
			return err
		}},
		{"Invalid Request", func() error {
			_, err := client.CreateTask(ctx, &agenteco.CreateTaskRequest{
				Title: "", // Missing required
			})
			return err
		}},
	}

	for _, test := range testErrors {
		err := test.fn()
		if err != nil {
			fmt.Printf("%s:\n", test.name)

			// Check specific error types
			if agenteco.IsNotFound(err) {
				fmt.Println("  → Resource not found")
			}
			if agenteco.IsRateLimited(err) {
				fmt.Println("  → Rate limited")
			}
			if agenteco.IsTimeout(err) {
				fmt.Println("  → Request timed out")
			}
			if agenteco.IsRetryable(err) {
				fmt.Println("  → Error is retryable")
			}

			// Check for API error details
			var apiErr *agenteco.APIError
			if errors.As(err, &apiErr) {
				fmt.Printf("  → Status: %d\n", apiErr.StatusCode)
				fmt.Printf("  → Code: %s\n", apiErr.Code)
				fmt.Printf("  → Message: %s\n", apiErr.Message)
				fmt.Printf("  → Category: %s\n", apiErr.Category)
				fmt.Printf("  → Temporary: %v\n", apiErr.Temporary())
			}
		}
	}

	// === RETRY LOGIC ===
	fmt.Println("\n5. Implementing Retry Logic")

	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		fmt.Printf("  Attempt %d/%d\n", attempt, maxRetries)

		_, err := client.GetAgent(ctx, "test-agent")
		if err == nil {
			fmt.Println("  → Success!")
			break
		}

		lastErr = err

		if !agenteco.IsRetryable(err) {
			fmt.Println("  → Non-retryable error, stopping")
			break
		}

		// Check for retry-after
		if retryAfter := agenteco.GetRetryAfter(err); retryAfter > 0 {
			fmt.Printf("  → Retry after: %v\n", retryAfter)
			time.Sleep(retryAfter)
		} else {
			// Exponential backoff
			backoff := time.Duration(attempt*100) * time.Millisecond
			fmt.Printf("  → Backing off for %v\n", backoff)
			time.Sleep(backoff)
		}
	}

	if lastErr != nil {
		fmt.Printf("  → All retries failed: %v\n", lastErr)
	}

	// === ERROR CATEGORIZATION ===
	fmt.Println("\n6. Error Categories")

	categories := map[agenteco.ErrorCategory]string{
		agenteco.ErrorCategoryClient:     "Client Error",
		agenteco.ErrorCategoryServer:     "Server Error",
		agenteco.ErrorCategoryNetwork:    "Network Error",
		agenteco.ErrorCategoryTimeout:    "Timeout Error",
		agenteco.ErrorCategoryAuth:       "Authentication Error",
		agenteco.ErrorCategoryValidation: "Validation Error",
		agenteco.ErrorCategoryNotFound:   "Not Found Error",
		agenteco.ErrorCategoryRateLimit:  "Rate Limit Error",
	}

	for category, name := range categories {
		apiErr := &agenteco.APIError{
			StatusCode: http.StatusBadRequest,
			Code:       "TEST_ERROR",
			Message:    "Test error message",
			Category:   category,
		}
		fmt.Printf("  %s: %v\n", name, apiErr.Temporary())
	}

	// === CONTEXT CANCELLATION ===
	fmt.Println("\n7. Context Cancellation")

	shortCtx, shortCancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer shortCancel()

	// Give context time to expire
	time.Sleep(10 * time.Millisecond)

	_, err = client.GetEconomyStats(shortCtx)
	if err != nil {
		fmt.Printf("  Context error: %v\n", err)

		if agenteco.IsTimeout(err) {
			fmt.Println("  → Detected timeout error")
		}

		var timeoutErr *agenteco.TimeoutError
		if errors.As(err, &timeoutErr) {
			fmt.Printf("  → Timeout duration: %v\n", timeoutErr.Duration)
		}
	}

	// === NETWORK ERROR HANDLING ===
	fmt.Println("\n8. Network Error Handling")

	// Create client with invalid URL to simulate network error
	badClient, _ := agenteco.NewClient(&agenteco.ClientConfig{
		BaseURL: "http://invalid-hostname-that-does-not-exist:9999",
		Timeout: 2 * time.Second,
	})
	defer badClient.Close()

	_, err = badClient.Health(ctx)
	if err != nil {
		fmt.Printf("  Network error: %v\n", err)

		var netErr *agenteco.NetworkError
		if errors.As(err, &netErr) {
			fmt.Printf("  → URL: %s\n", netErr.URL)
			fmt.Printf("  → Cause: %v\n", netErr.Cause)
		}
	}

	// === CLIENT ERROR HANDLING ===
	fmt.Println("\n9. Client Error Handling")

	_, err = client.CreateAgent(ctx, nil)
	if err != nil {
		fmt.Printf("  Client error: %v\n", err)

		var clientErr *agenteco.ClientError
		if errors.As(err, &clientErr) {
			fmt.Printf("  → Message: %s\n", clientErr.Message)
			if clientErr.Cause != nil {
				fmt.Printf("  → Cause: %v\n", clientErr.Cause)
			}
		}
	}

	// === COMPREHENSIVE ERROR HANDLER ===
	fmt.Println("\n10. Comprehensive Error Handler Function")

	exampleErrors := []error{
		agenteco.ErrAgentNotFound,
		agenteco.ErrUnauthorized,
		agenteco.ErrRateLimited,
		&agenteco.APIError{
			StatusCode: http.StatusInternalServerError,
			Code:       "SERVER_ERROR",
			Message:    "Internal server error",
			Category:   agenteco.ErrorCategoryServer,
		},
	}

	for _, err := range exampleErrors {
		result := comprehensiveErrorHandler(err)
		fmt.Printf("  %s\n", result)
	}

	fmt.Println("\n=== Error Handling Examples Complete ===")
}

// handleError demonstrates basic error handling
func handleError(err error) {
	if agenteco.IsNotFound(err) {
		fmt.Printf("  → Resource not found: %v\n", err)
		return
	}

	if agenteco.IsRateLimited(err) {
		retryAfter := agenteco.GetRetryAfter(err)
		fmt.Printf("  → Rate limited, retry after %v: %v\n", retryAfter, err)
		return
	}

	var apiErr *agenteco.APIError
	if errors.As(err, &apiErr) {
		fmt.Printf("  → API Error [%d] %s: %s\n",
			apiErr.StatusCode, apiErr.Code, apiErr.Message)
		return
	}

	fmt.Printf("  → Error: %v\n", err)
}

// comprehensiveErrorHandler provides a complete error handling strategy
func comprehensiveErrorHandler(err error) string {
	if err == nil {
		return "No error"
	}

	// Check for specific error types
	switch {
	case agenteco.IsNotFound(err):
		return "NOT_FOUND: The requested resource does not exist"

	case agenteco.IsRateLimited(err):
		retryAfter := agenteco.GetRetryAfter(err)
		return fmt.Sprintf("RATE_LIMITED: Retry after %v", retryAfter)

	case agenteco.IsTimeout(err):
		return "TIMEOUT: The request timed out"

	case agenteco.IsRetryable(err):
		return "RETRYABLE: The error is temporary, retry recommended"
	}

	// Check for API error
	var apiErr *agenteco.APIError
	if errors.As(err, &apiErr) {
		switch apiErr.Category {
		case agenteco.ErrorCategoryAuth:
			return fmt.Sprintf("AUTH_ERROR: %s", apiErr.Message)

		case agenteco.ErrorCategoryValidation:
			return fmt.Sprintf("VALIDATION_ERROR: %s", apiErr.Message)

		case agenteco.ErrorCategoryServer:
			if apiErr.Temporary() {
				return fmt.Sprintf("SERVER_ERROR (temporary): %s", apiErr.Message)
			}
			return fmt.Sprintf("SERVER_ERROR: %s", apiErr.Message)

		default:
			return fmt.Sprintf("API_ERROR [%d]: %s", apiErr.StatusCode, apiErr.Message)
		}
	}

	// Check for network error
	var netErr *agenteco.NetworkError
	if errors.As(err, &netErr) {
		return fmt.Sprintf("NETWORK_ERROR: %s", netErr.Message)
	}

	// Check for client error
	var clientErr *agenteco.ClientError
	if errors.As(err, &clientErr) {
		return fmt.Sprintf("CLIENT_ERROR: %s", clientErr.Message)
	}

	return fmt.Sprintf("UNKNOWN_ERROR: %v", err)
}
