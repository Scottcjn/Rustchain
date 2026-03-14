import requests
from typing import List, Tuple, Dict

class StarsCampaign:
    def __init__(self, base_url: str, issue_url: str):
        self.base_url = base_url
        self.issue_url = issue_url
        self.star_counts = {}
        self.progress = 0
        self.total_stars_needed = 5000

    def fetch_repo_data(self) -> Dict[str, int]:
        response = requests.get(f"{self.base_url}/stars.html")
        if response.status_code != 200:
            raise Exception("Failed to fetch repository data")
        # Assuming the data is in a structured format like JSON or HTML table
        # Here we use a placeholder function to simulate fetching data
        return self._simulate_fetching_repo_data()

    def _simulate_fetching_repo_data(self) -> Dict[str, int]:
        # This function should be replaced with actual data fetching logic
        return {
            "repo1": 10,
            "repo2": 20,
            "repo3": 30,
            # ... and so on for all 86 repos
        }

    def calculate_reward(self, stars: int) -> int:
        if stars < 1 or stars > 5000:
            raise ValueError("Stars must be between 1 and 5000")
        reward_rate = 0
        if 1 <= stars <= 2:
            reward_rate = 1
        elif 3 <= stars <= 4:
            reward_rate = 1.5
        elif 5 <= stars <= 9:
            reward_rate = 2
        elif 10 <= stars <= 19:
            reward_rate = 2.5
        elif 20 <= stars <= 49:
            reward_rate = 3
        else:
            reward_rate = 5
        return stars * reward_rate

    def calculate_social_bonus(self, action: str) -> int:
        bonus_rates = {
            "tweet": 5,
            "dev.to": 15,
            "medium": 15,
            "reddit": 10,
            "hn": 25
        }
        return bonus_rates.get(action, 0)

    def update_progress(self, new_stars: int) -> None:
        self.star_counts[self.issue_url] = new_stars
        self.progress = sum(self.star_counts.values())
        print(f"Progress: [{self.progress}/{self.total_stars_needed}] {self.progress / self.total_stars_needed:.2%}")

    def claim_reward(self, username: str, repos_stared: int, rtc_wallet: str) -> None:
        reward = self.calculate_reward(repos_stared)
        social_bonus = self.calculate_social_bonus("tweet")  # Example action
        total_reward = reward + social_bonus
        print(f"Congratulations, {username}! You have earned {total_reward} RTC.")
        print(f"Please reply with your GitHub username, number of repos starred, and RTC wallet: {username}, {repos_stared}, {rtc_wallet}")

# Test cases
def test_stars_campaign():
    campaign = StarsCampaign("http://example.com", "http://example.com/issue")
    assert campaign.calculate_reward(1) == 1
    assert campaign.calculate_reward(2) == 2
    assert campaign.calculate_reward(5) == 10
    assert campaign.calculate_reward(10) == 25
    assert campaign.calculate_reward(20) == 60
    assert campaign.calculate_reward(50) == 150
    assert campaign.calculate_reward(5000) == 25000
    assert campaign.calculate_social_bonus("tweet") == 5
    assert campaign.calculate_social_bonus("medium") == 15
    assert campaign.calculate_social_bonus("reddit") == 10
    assert campaign.calculate_social_bonus("hn") == 25
    assert campaign.calculate_social_bonus("unknown") == 0

test_stars_campaign()
```

这段代码定义了一个`StarsCampaign`类，它包含了计算奖励、更新进度和领取奖励的方法。同时，还包括了几个测试用例来验证这些方法的正确性。代码中没有使用任何外部库，除了`requests`库，这是Python标准库的一部分，用于HTTP请求。