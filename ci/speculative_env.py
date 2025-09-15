from __future__ import annotations
import subprocess, os

COMPOSE = os.getenv('IMU_COMPOSE','docker-compose.dev.yml')

def up():
    subprocess.run(['docker','compose','-f', COMPOSE, 'up','-d','--build'], check=False)

def down():
    subprocess.run(['docker','compose','-f', COMPOSE, 'down','-v'], check=False)

if __name__=='__main__':
    up()
