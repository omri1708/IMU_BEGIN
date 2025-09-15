from __future__ import annotations
import os, httpx
class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv('GITHUB_TOKEN','')
        self.http = httpx.Client(headers={'Authorization': f'token {self.token}', 'Accept':'application/vnd.github+json'})
    def create_issue(self, repo: str, title: str, body: str=''):
        owner, name = repo.split('/')
        return self.http.post(f'https://api.github.com/repos/{owner}/{name}/issues', json={'title': title,'body': body}).json()
