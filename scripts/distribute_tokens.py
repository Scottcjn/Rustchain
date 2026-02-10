import os
import requests

# GitHub API token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = "Scottcjn/Rustchain"
ISSUE_NUMBER = 47

def get_stars_and_comments():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    # Fetch stargazers
    stars_url = f"https://api.github.com/repos/{REPO}/stargazers"
    stargazers = requests.get(stars_url, headers=headers).json()
    
    # Fetch issue comments
    comments_url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments"
    comments = requests.get(comments_url, headers=headers).json()
    
    return stargazers, comments

def distribute_tokens():
    stargazers, comments = get_stars_and_comments()
    claimed_users = set()
    
    for comment in comments:
        username = comment["user"]["login"]
        if username in claimed_users:
            continue
        claimed_users.add(username)
        # Logic to send 2 RTC to the user's wallet (pseudo code)
        send_rtc(username)

def send_rtc(username):
    # Placeholder for sending RTC to the user
    print(f"Sending 2 RTC to {username}")

if __name__ == "__main__":
    distribute_tokens()