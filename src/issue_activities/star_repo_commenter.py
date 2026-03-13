import requests
import json

# Function to star the repository and comment the reason on the issue
class StarRepoAndComment:
    def __init__(self, repo_owner, repo_name, issue_number, reason, token):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.issue_number = issue_number
        self.reason = reason
        self.token = token
        self.base_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}'

    def star_repo(self):
        url = f'{self.base_url}/stargazers'
        headers = {
            'Authorization': f'token {self.token}'
        }
        response = requests.put(url, headers=headers)
        if response.status_code == 204:
            print('Repository starred successfully.')
        else:
            print(f'Failed to star repository. Status code: {response.status_code}')

    def comment_on_issue(self):
        url = f'{self.base_url}/issues/{self.issue_number}/comments'
        headers = {
            'Authorization': f'token {self.token}'
        }
        payload = {
            'body': self.reason
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 201:
            print('Comment posted successfully.')
        else:
            print(f'Failed to post comment. Status code: {response.status_code}')

    def execute(self):
        self.star_repo()
        self.comment_on_issue()


# Example Usage
if __name__ == '__main__':
    repo_owner = 'Scottcjn'
    repo_name = 'Rustchain'
    issue_number = 1  # Replace with the actual issue number
    reason = 'This repository demonstrates a unique consensus algorithm and is a great contribution to the blockchain ecosystem.'
    token = 'your_github_token_here'  # Replace with your GitHub token

    star_repo_and_commenter = StarRepoAndComment(repo_owner, repo_name, issue_number, reason, token)
    star_repo_and_commenter.execute()