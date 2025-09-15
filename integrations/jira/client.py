from __future__ import annotations
import os, httpx
class JiraClient:
    def __init__(self, base: str | None = None, token: str | None = None, email: str | None = None):
        self.base = base or os.getenv('JIRA_BASE','')
        self.email = email or os.getenv('JIRA_EMAIL','')
        self.token = token or os.getenv('JIRA_API_TOKEN','')
        self.http = httpx.Client(auth=(self.email, self.token))
    def create_issue(self, project: str, summary: str, issue_type: str='Task'):
        return self.http.post(self.base+'/rest/api/3/issue', json={'fields':{'project':{'key':project},'summary':summary,'issuetype':{'name':issue_type}}}).json()
