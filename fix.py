from datetime import date

def generate_blog_post(repo: str, ver: str, author: str) -> str:
    today = date.today().strftime("%B %d, %Y")
    
    header = f"# {repo}"
    separator = "---"
    meta = f"\n\n**Date:** {today}\n\n---"
    
    intro = f"""
## Why {repo}?
A seamless blend of memory safety and Pythonic elegance.

### Quick Statistics
| Metric       | Value       |
|--------------|-------------|
| Version      | {ver}       |
| Repository   | {repo}      |
| Contributors | 30+         |"""
    
    setup = f"""
## Getting Started
```bash
pip install {repo}
python main.py
```"""

    conclusion = f"""
## Conclusion
If you seek performance without complexity, {repo} is the answer.
---
"""
    
    body = f"{header}{meta}\n{intro}{meta}\n{setup}{conclusion}"
    return body

if __name__ == "__main__":
    content = generate_blog_post("RustChain", "1.4.0", "Scottcjn")
    print(content)