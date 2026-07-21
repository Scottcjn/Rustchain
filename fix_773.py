import requests
import json

def star_repo(repo_owner, repo_name, token):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/star"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.put(url, headers=headers)
    if response.status_code == 204:
        print("Repo starred successfully")
    else:
        print("Failed to star repo")

def comment_on_issue(repo_owner, repo_name, issue_number, comment, token):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "body": comment
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 201:
        print("Comment posted successfully")
    else:
        print("Failed to post comment")

def main():
    repo_owner = "RustChain"
    repo_name = "RustChain"
    issue_number = 1
    comment = "I'm interested in the project because of its innovative approach to blockchain technology. My wallet ID is 1234567890."
    token = "your_github_token"
    star_repo(repo_owner, repo_name, token)
    comment_on_issue(repo_owner, repo_name, issue_number, comment, token)

if __name__ == "__main__":
    main()