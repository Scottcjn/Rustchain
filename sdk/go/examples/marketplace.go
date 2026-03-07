// Example demonstrating marketplace operations.
// Run with: go run examples/marketplace.go
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

	// === LIST MARKETPLACE LISTINGS ===
	fmt.Println("=== Marketplace Listings ===")

	opts := &agenteco.ListOptions{
		Page:      1,
		Limit:     10,
		SortBy:    "total_hires",
		SortOrder: "desc",
	}

	listings, meta, err := client.ListListings(ctx, opts)
	if err != nil {
		log.Printf("Failed to list listings: %v", err)
	} else {
		fmt.Printf("Marketplace (Page %d of %d, Total: %d)\n",
			meta.CurrentPage, meta.TotalPages, meta.TotalItems)

		for i, listing := range listings {
			priceIcon := "🏷️"
			switch listing.PriceType {
			case agenteco.PriceTypeHourly:
				priceIcon = "⏱️"
			case agenteco.PriceTypeAuction:
				priceIcon = "🔨"
			case agenteco.PriceTypeDynamic:
				priceIcon = "📊"
			}

			rating := "⭐"
			if listing.AverageRating > 0 {
				rating = fmt.Sprintf("⭐ %.1f", listing.AverageRating)
			}

			fmt.Printf("%d. %s - %s%s %.2f %s | Hires: %d | %s\n",
				i+1, listing.Title, priceIcon, listing.Price, listing.Currency,
				listing.TotalHires, rating)
			fmt.Printf("   Category: %s | Status: %s\n",
				listing.Category, listing.Status)
		}
	}

	// === GET SPECIFIC LISTING ===
	fmt.Println("\n=== Getting Listing Details ===")

	if len(listings) > 0 {
		listing, err := client.GetListing(ctx, listings[0].ListingID)
		if err != nil {
			log.Printf("Failed to get listing: %v", err)
		} else {
			fmt.Printf("Listing: %s\n", listing.Title)
			fmt.Printf("  Description: %s\n", listing.Description)
			fmt.Printf("  Agent: %s\n", listing.AgentID)
			fmt.Printf("  Owner: %s\n", listing.Owner)
			fmt.Printf("  Category: %s\n", listing.Category)
			fmt.Printf("  Price: %.2f %s (%s)\n",
				listing.Price, listing.Currency, listing.PriceType)
			fmt.Printf("  Total Hires: %d\n", listing.TotalHires)
			fmt.Printf("  Average Rating: %.1f/5.0\n", listing.AverageRating)
			fmt.Printf("  Created: %s\n", listing.CreatedAt.Format(time.RFC3339))
			fmt.Printf("  Updated: %s\n", listing.UpdatedAt.Format(time.RFC3339))
		}
	}

	// === CREATE LISTING ===
	fmt.Println("\n=== Creating Marketplace Listing ===")

	// First, we need an agent to list
	agents, _, err := client.ListAgents(ctx, &agenteco.ListOptions{Limit: 1})
	if err != nil || len(agents) == 0 {
		log.Println("No agents available to create listing")
	} else {
		agentID := agents[0].AgentID

		createReq := &agenteco.CreateListingRequest{
			AgentID:     agentID,
			Title:       fmt.Sprintf("Data Processing Service %d", time.Now().Unix()%10000),
			Description: "Professional data processing with 99.9% accuracy guarantee",
			Category:    "data-processing",
			PriceType:   agenteco.PriceTypeFixed,
			Price:       12.5,
			Currency:    "RTC",
		}

		listing, err := client.CreateListing(ctx, createReq)
		if err != nil {
			log.Printf("Failed to create listing: %v", err)
		} else {
			fmt.Printf("Created listing: %s (ID: %s)\n", listing.Title, listing.ListingID)
			fmt.Printf("  Price: %.2f %s\n", listing.Price, listing.Currency)
			fmt.Printf("  Status: %s\n", listing.Status)
		}
	}

	// === LIST BY CATEGORY ===
	fmt.Println("\n=== Listings by Category ===")

	categories := []string{"compute", "storage", "data-processing", "validation"}

	for _, category := range categories {
		opts := &agenteco.ListOptions{
			Limit: 3,
			Filter: map[string]string{
				"category": category,
			},
		}

		listings, meta, err := client.ListListings(ctx, opts)
		if err != nil {
			continue
		}

		if meta.TotalItems > 0 {
			fmt.Printf("%s: %d listings\n", category, meta.TotalItems)
			for _, l := range listings {
				fmt.Printf("  - %s (%.2f RTC)\n", l.Title, l.Price)
			}
		}
	}

	// === UPDATE LISTING ===
	fmt.Println("\n=== Updating Listing ===")

	if len(listings) > 0 {
		updateReq := &agenteco.UpdateListingRequest{
			Price: listings[0].Price * 0.9, // 10% discount
		}

		updated, err := client.UpdateListing(ctx, listings[0].ListingID, updateReq)
		if err != nil {
			log.Printf("Failed to update listing: %v", err)
		} else {
			fmt.Printf("Updated price: %.2f -> %.2f RTC\n",
				listings[0].Price, updated.Price)
		}
	}

	// === HIRE AGENT FROM MARKETPLACE ===
	fmt.Println("\n=== Hiring Agent from Marketplace ===")

	if len(listings) > 0 {
		hireReq := &agenteco.CreateTaskRequest{
			Title:       fmt.Sprintf("Quick Task %d", time.Now().Unix()%10000),
			Description: "One-time data processing task",
			Type:        agenteco.TaskTypeComputation,
			Priority:    7,
			Reward:      listings[0].Price,
			Deadline:    time.Now().Add(6 * time.Hour),
			Metadata: map[string]interface{}{
				"source":     "marketplace_hire",
				"listing_id": listings[0].ListingID,
			},
		}

		task, err := client.HireAgent(ctx, listings[0].ListingID, hireReq)
		if err != nil {
			log.Printf("Failed to hire agent: %v", err)
		} else {
			fmt.Printf("Hired agent from listing: %s\n", listings[0].Title)
			fmt.Printf("Created task: %s (ID: %s)\n", task.Title, task.TaskID)
			fmt.Printf("  Reward: %.2f RTC\n", task.Reward)
			fmt.Printf("  Status: %s\n", task.Status)
		}
	}

	// === PRICE TYPE ANALYSIS ===
	fmt.Println("\n=== Price Type Distribution ===")

	priceTypes := []agenteco.PriceType{
		agenteco.PriceTypeFixed,
		agenteco.PriceTypeHourly,
		agenteco.PriceTypeAuction,
		agenteco.PriceTypeDynamic,
	}

	for _, pt := range priceTypes {
		opts := &agenteco.ListOptions{
			Limit: 1,
			Filter: map[string]string{
				"price_type": string(pt),
			},
		}

		_, meta, err := client.ListListings(ctx, opts)
		if err != nil {
			continue
		}

		fmt.Printf("%s: %d listings\n", pt, meta.TotalItems)
	}

	fmt.Println("\n=== Marketplace Operations Complete ===")
}
