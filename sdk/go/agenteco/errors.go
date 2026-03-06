package agenteco

import (
	"errors"
	"fmt"
	"net/http"
	"time"
)

// Common errors that may be returned by the SDK.
var (
	// ErrAgentNotFound is returned when an agent does not exist.
	ErrAgentNotFound = errors.New("agent not found")
	// ErrTaskNotFound is returned when a task does not exist.
	ErrTaskNotFound = errors.New("task not found")
	// ErrInvalidAgentID is returned when an agent ID is malformed.
	ErrInvalidAgentID = errors.New("invalid agent ID")
	// ErrInvalidTaskID is returned when a task ID is malformed.
	ErrInvalidTaskID = errors.New("invalid task ID")
	// ErrUnauthorized is returned when authentication fails.
	ErrUnauthorized = errors.New("unauthorized")
	// ErrForbidden is returned when access is denied.
	ErrForbidden = errors.New("forbidden")
	// ErrRateLimited is returned when the rate limit is exceeded.
	ErrRateLimited = errors.New("rate limit exceeded")
	// ErrServerError is returned when the server encounters an error.
	ErrServerError = errors.New("internal server error")
	// ErrServiceUnavailable is returned when the service is temporarily unavailable.
	ErrServiceUnavailable = errors.New("service unavailable")
	// ErrInvalidRequest is returned when the request is malformed.
	ErrInvalidRequest = errors.New("invalid request")
	// ErrDuplicateAgent is returned when registering an agent that already exists.
	ErrDuplicateAgent = errors.New("agent already exists")
	// ErrInsufficientFunds is returned when a wallet lacks sufficient balance.
	ErrInsufficientFunds = errors.New("insufficient funds")
	// ErrTaskAlreadyAssigned is returned when assigning an already assigned task.
	ErrTaskAlreadyAssigned = errors.New("task already assigned")
	// ErrInvalidAgentStatus is returned when an agent status transition is invalid.
	ErrInvalidAgentStatus = errors.New("invalid agent status transition")
	// ErrDeadlineExceeded is returned when an operation times out.
	ErrDeadlineExceeded = errors.New("deadline exceeded")
	// ErrConnectionFailed is returned when a connection cannot be established.
	ErrConnectionFailed = errors.New("connection failed")
	// ErrInvalidResponse is returned when the server response is malformed.
	ErrInvalidResponse = errors.New("invalid server response")
	// ErrRetryExhausted is returned when all retry attempts have failed.
	ErrRetryExhausted = errors.New("retry attempts exhausted")
)

// ErrorCategory categorizes errors for handling purposes.
type ErrorCategory string

const (
	// ErrorCategoryClient indicates a client-side error.
	ErrorCategoryClient ErrorCategory = "client"
	// ErrorCategoryServer indicates a server-side error.
	ErrorCategoryServer ErrorCategory = "server"
	// ErrorCategoryNetwork indicates a network-related error.
	ErrorCategoryNetwork ErrorCategory = "network"
	// ErrorCategoryTimeout indicates a timeout error.
	ErrorCategoryTimeout ErrorCategory = "timeout"
	// ErrorCategoryAuth indicates an authentication error.
	ErrorCategoryAuth ErrorCategory = "auth"
	// ErrorCategoryValidation indicates a validation error.
	ErrorCategoryValidation ErrorCategory = "validation"
	// ErrorCategoryNotFound indicates a resource was not found.
	ErrorCategoryNotFound ErrorCategory = "not_found"
	// ErrorCategoryRateLimit indicates a rate limiting error.
	ErrorCategoryRateLimit ErrorCategory = "rate_limit"
)

// APIError represents an error returned by the API.
type APIError struct {
	// StatusCode is the HTTP status code.
	StatusCode int `json:"status_code"`
	// Code is the application-specific error code.
	Code string `json:"code"`
	// Message is a human-readable error message.
	Message string `json:"message"`
	// Details provides additional error context.
	Details map[string]interface{} `json:"details,omitempty"`
	// Category categorizes the error type.
	Category ErrorCategory `json:"category"`
	// RetryAfter indicates when to retry (for rate limits).
	RetryAfter time.Duration `json:"retry_after,omitempty"`
	// Raw contains the raw error response.
	Raw interface{} `json:"-"`
}

// Error implements the error interface.
func (e *APIError) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("agenteco: %s (HTTP %d): %s", e.Code, e.StatusCode, e.Message)
	}
	return fmt.Sprintf("agenteco: HTTP %d: %s", e.StatusCode, e.Message)
}

// Is implements errors.Is for error type checking.
func (e *APIError) Is(target error) bool {
	switch target {
	case ErrAgentNotFound, ErrTaskNotFound:
		return e.StatusCode == http.StatusNotFound
	case ErrUnauthorized:
		return e.StatusCode == http.StatusUnauthorized
	case ErrForbidden:
		return e.StatusCode == http.StatusForbidden
	case ErrRateLimited:
		return e.StatusCode == http.StatusTooManyRequests
	case ErrServerError:
		return e.StatusCode >= http.StatusInternalServerError
	case ErrInvalidRequest:
		return e.StatusCode == http.StatusBadRequest
	}
	return false
}

// Temporary indicates if the error is temporary and retrying may help.
func (e *APIError) Temporary() bool {
	switch e.Category {
	case ErrorCategoryNetwork, ErrorCategoryTimeout, ErrorCategoryRateLimit:
		return true
	case ErrorCategoryServer:
		return e.StatusCode == http.StatusServiceUnavailable ||
			e.StatusCode == http.StatusBadGateway ||
			e.StatusCode == http.StatusGatewayTimeout
	}
	return false
}

// ClientError represents a client-side error.
type ClientError struct {
	// Message is a human-readable error message.
	Message string
	// Cause is the underlying error (if any).
	Cause error
}

// Error implements the error interface.
func (e *ClientError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("agenteco: client error: %s: %v", e.Message, e.Cause)
	}
	return fmt.Sprintf("agenteco: client error: %s", e.Message)
}

// Unwrap returns the underlying error.
func (e *ClientError) Unwrap() error {
	return e.Cause
}

// NetworkError represents a network-related error.
type NetworkError struct {
	// Message is a human-readable error message.
	Message string
	// URL is the request URL that failed.
	URL string
	// Cause is the underlying error.
	Cause error
}

// Error implements the error interface.
func (e *NetworkError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("agenteco: network error: %s (%s): %v", e.Message, e.URL, e.Cause)
	}
	return fmt.Sprintf("agenteco: network error: %s (%s)", e.Message, e.URL)
}

// Unwrap returns the underlying error.
func (e *NetworkError) Unwrap() error {
	return e.Cause
}

// TimeoutError represents a timeout error.
type TimeoutError struct {
	// Message is a human-readable error message.
	Message string
	// Duration is the timeout duration.
	Duration time.Duration
	// Cause is the underlying error.
	Cause error
}

// Error implements the error interface.
func (e *TimeoutError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("agenteco: timeout after %v: %s: %v", e.Duration, e.Message, e.Cause)
	}
	return fmt.Sprintf("agenteco: timeout after %v: %s", e.Duration, e.Message)
}

// Unwrap returns the underlying error.
func (e *TimeoutError) Unwrap() error {
	return e.Cause
}

// IsTimeout checks if an error is a timeout error.
func IsTimeout(err error) bool {
	var te *TimeoutError
	return errors.As(err, &te)
}

// IsNotFound checks if an error indicates a resource was not found.
func IsNotFound(err error) bool {
	var apiErr *APIError
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode == http.StatusNotFound
	}
	return errors.Is(err, ErrAgentNotFound) || errors.Is(err, ErrTaskNotFound)
}

// IsRateLimited checks if an error indicates rate limiting.
func IsRateLimited(err error) bool {
	var apiErr *APIError
	if errors.As(err, &apiErr) {
		return apiErr.StatusCode == http.StatusTooManyRequests
	}
	return errors.Is(err, ErrRateLimited)
}

// IsRetryable checks if an error is retryable.
func IsRetryable(err error) bool {
	if IsTimeout(err) || IsRateLimited(err) {
		return true
	}
	var apiErr *APIError
	if errors.As(err, &apiErr) {
		return apiErr.Temporary()
	}
	var netErr *NetworkError
	return errors.As(err, &netErr)
}

// GetRetryAfter extracts the retry-after duration from an error.
func GetRetryAfter(err error) time.Duration {
	var apiErr *APIError
	if errors.As(err, &apiErr) {
		return apiErr.RetryAfter
	}
	return 0
}

// NewAPIError creates a new API error from HTTP response details.
func NewAPIError(statusCode int, code, message string, details map[string]interface{}) *APIError {
	return &APIError{
		StatusCode: statusCode,
		Code:       code,
		Message:    message,
		Details:    details,
		Category:   categorizeError(statusCode),
	}
}

// categorizeError determines the error category from HTTP status code.
func categorizeError(statusCode int) ErrorCategory {
	switch statusCode {
	case http.StatusBadRequest:
		return ErrorCategoryValidation
	case http.StatusUnauthorized:
		return ErrorCategoryAuth
	case http.StatusForbidden:
		return ErrorCategoryAuth
	case http.StatusNotFound:
		return ErrorCategoryNotFound
	case http.StatusTooManyRequests:
		return ErrorCategoryRateLimit
	case http.StatusInternalServerError,
		http.StatusBadGateway,
		http.StatusServiceUnavailable,
		http.StatusGatewayTimeout:
		return ErrorCategoryServer
	default:
		if statusCode >= 400 && statusCode < 500 {
			return ErrorCategoryClient
		}
		return ErrorCategoryServer
	}
}
