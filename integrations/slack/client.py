from __future__ import annotations
import os, httpx

class SlackClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv('SLACK_BOT_TOKEN','')
        self.http = httpx.Client(headers={'Authorization': f'Bearer {self.token}'})
    def post_message(self, channel: str, text: str):
        return self.http.post('https://slack.com/api/chat.postMessage', json={'channel': channel, 'text': text}).json()
