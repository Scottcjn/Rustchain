```python
from github import Github
from github.GithubException import GithubException
import requests
import os

# Constants
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
REPO_NAME = 'owner/RustChain'
RTC_REWARD = 10
REWARD_NOTIFICATION_URL = 'https://api.example.com/reward'

def setup_repository():
    """Setup the repository with necessary labels and contributing guidelines."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        # Ensure CONTRIBUTING.md exists
        contributing_file = repo.get_contents("CONTRIBUTING.md")
        if not contributing_file:
            repo.create_file("CONTRIBUTING.md", "Add contributing guidelines", "Content for contributing guidelines")

        # Create labels
        labels = repo.get_labels()
        existing_labels = [label.name for label in labels]
        required_labels = ['good first issue', 'help wanted']
        
        for label in required_labels:
            if label not in existing_labels:
                repo.create_label(name=label, color='0e8a16')
    except GithubException as e:
        print(f"Error setting up repository: {e}")

def is_first_contribution(pr):
    """Check if the PR is the contributor's first merged PR."""
    try:
        user = pr.user
        user_prs = user.get_pulls(state='closed', base=REPO_NAME)
        return len([p for p in user_prs if p.merged]) == 1
    except GithubException as e:
        print(f"Error checking first contribution: {e}")
        return False

def reward_contributor(pr):
    """Send reward notification if the PR is valid and first."""
    if is_first_contribution(pr):
        try:
            response = requests.post(REWARD_NOTIFICATION_URL, json={
                'username': pr.user.login,
                'reward': RTC_REWARD
            })
            if response.status_code == 200:
                print(f"Reward notification sent for {pr.user.login}")
            else:
                print(f"Failed to send reward notification: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error sending reward notification: {e}")

def handle_pull_request_event(event):
    """Handle GitHub pull request event."""
    if event['action'] == 'closed' and event['pull_request']['merged']:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        pr = repo.get_pull(event['pull_request']['number'])
        reward_contributor(pr)

def main():
    """Main function to setup repository and listen for events."""
    setup_repository()
    # This would be replaced by actual event listening logic
    # For example, using a webhook to listen to GitHub events
    # handle_pull_request_event(event)

if __name__ == "__main__":
    main()
```

This code sets up the repository for contributions, checks if a pull request is a contributor's first, and sends a reward notification if applicable. It uses the `PyGithub` library to interact with GitHub and `requests` to send notifications. The `main` function initializes the setup, and the event handling logic would be integrated with a webhook listener in a real-world scenario.