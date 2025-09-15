from __future__ import annotations
from alembic import command
from alembic.config import Config
from pathlib import Path

def autogen(message: str = 'spec update'):
    cfg = Config('alembic.ini')
    cfg.set_main_option('script_location', 'alembic')
    command.revision(cfg, message=message, autogenerate=True)
    command.upgrade(cfg, 'head')

if __name__ == '__main__':
    autogen()
