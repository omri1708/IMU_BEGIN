from __future__ import annotations
import os, httpx
class NotionClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv('NOTION_TOKEN','')
        self.http = httpx.Client(headers={'Authorization': f'Bearer {self.token}','Notion-Version':'2022-06-28'})
    def create_page(self, parent_db: str, title: str):
        return self.http.post('https://api.notion.com/v1/pages', json={'parent':{'database_id':parent_db},'properties':{'Name':{'title':[{'text':{'content':title}}]}}}).json()
