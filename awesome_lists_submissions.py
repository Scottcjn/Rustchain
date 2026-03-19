// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import requests
import json
import time
import os
from datetime import datetime
import base64

DB_PATH = 'rustchain.db'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

class AwesomeListSubmitter:
    def __init__(self):
        self.headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'RustChain-Bot'
        }
        self.rustchain_description = "Decentralized blockchain platform with AI integration and smart contract capabilities"
        self.bottube_description = "AI-powered video content analysis and blockchain verification system"
        self.beacon_skill_description = "Blockchain-based skill verification and credentialing platform"
        
    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS awesome_submissions (
                    id INTEGER PRIMARY KEY,
                    repo_owner TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pr_number INTEGER,
                    status TEXT DEFAULT 'pending',
                    stars INTEGER,
                    description TEXT
                )
            ''')
            conn.commit()

    def search_awesome_repos(self, keywords, min_stars=100):
        """Search for awesome-* repositories with specific keywords"""
        awesome_repos = []
        
        for keyword in keywords:
            query = f"awesome {keyword} in:name,description stars:>={min_stars}"
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
            
            try:
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    for repo in data.get('items', [])[:10]:  # Top 10 per keyword
                        awesome_repos.append({
                            'owner': repo['owner']['login'],
                            'name': repo['name'],
                            'stars': repo['stargazers_count'],
                            'description': repo['description'],
                            'category': keyword
                        })
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"Error searching for {keyword}: {e}")
                
        return awesome_repos

    def get_readme_content(self, owner, repo):
        """Fetch README content from repository"""
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                content = response.json()['content']
                return base64.b64decode(content).decode('utf-8')
        except Exception as e:
            print(f"Error fetching README for {owner}/{repo}: {e}")
        
        return None

    def find_insertion_point(self, readme_content, project_name):
        """Find appropriate section to insert project"""
        lines = readme_content.split('\n')
        
        # Look for relevant sections
        blockchain_sections = ['blockchain', 'cryptocurrency', 'crypto', 'bitcoin', 'ethereum']
        ai_sections = ['ai', 'artificial intelligence', 'machine learning', 'ml', 'neural']
        
        project_keywords = {
            'RustChain': blockchain_sections + ['rust', 'smart contract'],
            'BoTTube': ai_sections + ['video', 'content', 'analysis'],
            'beacon-skill': blockchain_sections + ['skill', 'credential', 'verification']
        }
        
        keywords = project_keywords.get(project_name, blockchain_sections)
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                if line.startswith('##') or line.startswith('#'):
                    # Found a relevant section, look for the end or a good insertion point
                    for j in range(i+1, len(lines)):
                        if lines[j].strip().startswith('- [') or lines[j].strip().startswith('* ['):
                            continue
                        elif lines[j].strip() == '':
                            return j
                        elif lines[j].startswith('#'):
                            return j-1
                    return len(lines)
        
        # If no specific section found, add to end
        return len(lines)

    def generate_project_entry(self, project_name):
        """Generate markdown entry for project"""
        entries = {
            'RustChain': f"- [RustChain](https://github.com/Scottcjn/Rustchain) - {self.rustchain_description}",
            'BoTTube': f"- [BoTTube](https://github.com/Scottcjn/BoTTube) - {self.bottube_description}",
            'beacon-skill': f"- [beacon-skill](https://github.com/Scottcjn/beacon-skill) - {self.beacon_skill_description}"
        }
        return entries.get(project_name, "")

    def create_pull_request(self, owner, repo, project_name):
        """Create pull request to add project to awesome list"""
        
        # Get current README
        readme_content = self.get_readme_content(owner, repo)
        if not readme_content:
            return None
            
        # Check if project already exists
        if project_name.lower() in readme_content.lower():
            print(f"{project_name} already exists in {owner}/{repo}")
            return None
            
        # Find insertion point and create new content
        lines = readme_content.split('\n')
        insertion_point = self.find_insertion_point(readme_content, project_name)
        project_entry = self.generate_project_entry(project_name)
        
        new_lines = lines[:insertion_point] + [project_entry] + lines[insertion_point:]
        new_content = '\n'.join(new_lines)
        
        # Create branch and commit
        branch_name = f"add-{project_name.lower()}-{int(time.time())}"
        commit_message = f"Add {project_name} to awesome list"
        
        try:
            # Get master branch SHA
            master_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main"
            master_response = requests.get(master_url, headers=self.headers)
            if master_response.status_code != 200:
                master_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/master"
                master_response = requests.get(master_url, headers=self.headers)
            
            if master_response.status_code != 200:
                return None
                
            master_sha = master_response.json()['object']['sha']
            
            # Create new branch
            branch_data = {
                'ref': f'refs/heads/{branch_name}',
                'sha': master_sha
            }
            branch_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
            branch_response = requests.post(branch_url, headers=self.headers, json=branch_data)
            
            if branch_response.status_code != 201:
                return None
            
            # Get README file SHA
            readme_url = f"https://api.github.com/repos/{owner}/{repo}/contents/README.md"
            readme_response = requests.get(readme_url, headers=self.headers)
            readme_sha = readme_response.json()['sha']
            
            # Update README
            update_data = {
                'message': commit_message,
                'content': base64.b64encode(new_content.encode()).decode(),
                'sha': readme_sha,
                'branch': branch_name
            }
            
            update_response = requests.put(readme_url, headers=self.headers, json=update_data)
            
            if update_response.status_code not in [200, 201]:
                return None
            
            # Create pull request
            pr_data = {
                'title': f"Add {project_name} to awesome list",
                'body': f"""## Adding {project_name}

{self.generate_project_entry(project_name).replace('- [', '[').replace('] - ', '] - ')}

This PR adds {project_name} to your awesome list. The project is:
- Open source and actively maintained
- Well documented with clear README
- Has practical use cases in the blockchain/AI space
- Follows best practices for code quality

Thank you for maintaining this valuable resource for the community!""",
                'head': f"Scottcjn:{branch_name}",
                'base': 'main'
            }
            
            pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            pr_response = requests.post(pr_url, headers=self.headers, json=pr_data)
            
            if pr_response.status_code == 201:
                return pr_response.json()['number']
                
        except Exception as e:
            print(f"Error creating PR for {owner}/{repo}: {e}")
            
        return None

    def submit_to_awesome_lists(self):
        """Main function to submit projects to awesome lists"""
        self.init_db()
        
        keywords = ['blockchain', 'cryptocurrency', 'artificial-intelligence', 'machine-learning', 'rust']
        awesome_repos = self.search_awesome_repos(keywords)
        
        projects = ['RustChain', 'BoTTube', 'beacon-skill']
        
        with sqlite3.connect(DB_PATH) as conn:
            for repo in awesome_repos:
                for project in projects:
                    # Check if already submitted
                    existing = conn.execute(
                        'SELECT id FROM awesome_submissions WHERE repo_owner=? AND repo_name=? AND project_name=?',
                        (repo['owner'], repo['name'], project)
                    ).fetchone()
                    
                    if existing:
                        continue
                    
                    print(f"Submitting {project} to {repo['owner']}/{repo['name']} ({repo['stars']} stars)")
                    
                    pr_number = self.create_pull_request(repo['owner'], repo['name'], project)
                    
                    # Record submission
                    conn.execute('''
                        INSERT INTO awesome_submissions 
                        (repo_owner, repo_name, category, project_name, pr_number, stars, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        repo['owner'], repo['name'], repo['category'], project,
                        pr_number, repo['stars'], repo['description']
                    ))
                    
                    conn.commit()
                    
                    if pr_number:
                        print(f"✅ Created PR #{pr_number} for {project} in {repo['owner']}/{repo['name']}")
                    else:
                        print(f"❌ Failed to create PR for {project} in {repo['owner']}/{repo['name']}")
                    
                    time.sleep(5)  # Rate limiting

    def check_submission_status(self):
        """Check status of submitted PRs"""
        with sqlite3.connect(DB_PATH) as conn:
            submissions = conn.execute('''
                SELECT repo_owner, repo_name, project_name, pr_number, submission_date
                FROM awesome_submissions 
                WHERE status = 'pending' AND pr_number IS NOT NULL
            ''').fetchall()
            
            for owner, repo, project, pr_number, date in submissions:
                try:
                    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
                    response = requests.get(url, headers=self.headers)
                    
                    if response.status_code == 200:
                        pr_data = response.json()
                        state = pr_data['state']
                        merged = pr_data.get('merged', False)
                        
                        new_status = 'merged' if merged else state
                        
                        conn.execute(
                            'UPDATE awesome_submissions SET status=? WHERE repo_owner=? AND repo_name=? AND project_name=?',
                            (new_status, owner, repo, project)
                        )
                        
                        print(f"{project} in {owner}/{repo}: {new_status}")
                        
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error checking PR status: {e}")
            
            conn.commit()

    def generate_report(self):
        """Generate submission report"""
        with sqlite3.connect(DB_PATH) as conn:
            stats = conn.execute('''
                SELECT status, COUNT(*) as count 
                FROM awesome_submissions 
                GROUP BY status
            ''').fetchall()
            
            print("\n=== Awesome List Submission Report ===")
            for status, count in stats:
                print(f"{status.title()}: {count}")
            
            merged = conn.execute('''
                SELECT repo_owner, repo_name, project_name, pr_number
                FROM awesome_submissions 
                WHERE status = 'merged'
            ''').fetchall()
            
            if merged:
                print(f"\n🎉 Merged PRs (Earning {len(merged) * 3} RTC):")
                for owner, repo, project, pr_num in merged:
                    print(f"  - {project} in {owner}/{repo} (PR #{pr_num})")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable required")
        exit(1)
        
    submitter = AwesomeListSubmitter()
    
    print("🚀 Starting awesome list submissions...")
    submitter.submit_to_awesome_lists()
    
    print("\n📊 Checking submission status...")
    submitter.check_submission_status()
    
    submitter.generate_report()