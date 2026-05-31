```python
import blockchain  # Initialize blockchain module

# Define campaign parameters
pool_size = 5000  # Total RTC value in pool
total_stars_needed = 5000  # Total stars required for campaign
stars_across_repos = 337  # Current number of stars across all repositories
repos_listed = 86  # Number of repositories listed

# Calculate remaining RTCs needed
remaining_rtc_needed = total_stars_needed - stars_across_repos

# Define bonus structure
bonus_structure = {
    "1-2": {"rtc_per_star": 1, "max_payout": 2},
    "3-4": {"rtc_per_star": 1.5, "max_payout": 6},
    "5-9": {"rtc_per_star": 2, "max_payout": 18},
    "10-19": {"rtc_per_star": 2.5, "max_payout": 50}
}

# Function to calculate RTCs for each repository
def calculate_rtc_for_repo(stars):
    repo_rtc = stars * bonus_structure[repos_listed][f"{stars//repos_listed}-{(stars//repos_listed)+1}"]
    return repo_rtc

# Calculate RTCs needed for each repository and add to total RTC pool
total_pool_rtc = 0
for i in range(stars_across_repos, total_stars_needed):
    stars = i + 1
    repo_rtc = calculate_rtc_for_repo(stars)
    total_pool_rtc += repo_rtc

# Check if required RTCs exceed available pool
if total_pool_rtc > pool_size:
    print("Insufficient RTCs in the pool")
else:
    # Update blockchain with new campaign data
    blockchain.update_block(total_stars_needed, total_pool_rtc)
    
    # Print campaign statistics
    campaign_stats = f"Total Stars Needed: {total_stars_needed}\n"
    campaign_stats += f"Stars Across Repositories: {stars_across_repos}\n"
    campaign_stats += f"Remaining RTCs Needed: {remaining_rtc_needed}\n"
    campaign_stats += f"Total Pool RTC: {total_pool_rtc}"

print(campaign_stats)

# Calculate bonus for successful stars
bonus_structure_used = {}
for i in range(stars_across_repos, total_stars_needed):
    stars = i + 1
    if stars not in bonus_structure_used:
        bonus_structure_used[stars] = calculate_rtc_for_repo(stars)
    
print("Bonus Structure:")
for star, value in bonus_structure_used.items():
    print(f"{star}: {value}")
```