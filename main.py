
import time
from config import Config
from scanner import TaskScanner

def main():
    config = Config()
    scanner = TaskScanner(config)
    
    while True:
        tasks = scanner.scan()
        for task in tasks:
            process_task(task)
        time.sleep(config.RUN_INTERVAL)
