#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
录制 RustChain Discord Bot 演示视频
使用 Playwright 自动化演示所有命令
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import os
import glob
import shutil
import time

OUTPUT_DIR = "C:\\Users\\songs\\.openclaw\\media\\outbound"
OUTPUT_GIF = os.path.join(OUTPUT_DIR, "rustchain-bot-demo.gif")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def record_demo():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1280, "height": 720}
        )
        
        page = context.new_page()
        
        print("[录制] RustChain Discord Bot 演示")
        print("=" * 50)
        
        try:
            # Step 1: 打开 GitHub 仓库
            print("[1/6] 打开代码仓库...")
            page.goto("https://github.com/soongtv/rustchain-discord-bot", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            
            # Step 2: 展示 README
            print("[2/6] 展示项目说明...")
            page.evaluate("window.scrollTo(0, 500)")
            page.wait_for_timeout(1500)
            
            # Step 3: 打开 Bot 邀请链接
            print("[3/6] 打开 Discord Bot 邀请...")
            page.goto("https://discord.com/api/oauth2/authorize?client_id=1481195491424211077&permissions=274878024768&scope=bot%20applications.commands", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            
            # Step 4: 展示命令列表（输入 /）
            print("[4/6] 展示 Slash Commands 列表...")
            page.keyboard.type("/")
            page.wait_for_timeout(2000)
            
            # Step 5: 演示 /help 命令
            print("[5/6] 演示 /help 命令...")
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
            
            # Step 6: 回到 GitHub 总结
            print("[6/6] 返回 GitHub 总结...")
            page.goto("https://github.com/soongtv/rustchain-discord-bot", wait_until="networkidle", timeout=30000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(2000)
            
            print("=" * 50)
            print("OK: 录制完成！")
            
        except Exception as e:
            print(f"错误：{e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()
            
            # 转换为 GIF
            webm_files = glob.glob(os.path.join(OUTPUT_DIR, "*.webm"))
            if webm_files:
                latest_file = max(webm_files, key=os.path.getctime)
                print(f"\n视频已保存：{latest_file}")
                print(f"GIF 将保存到：{OUTPUT_GIF}")
            else:
                print("警告：未找到录制的视频文件")

if __name__ == "__main__":
    try:
        record_demo()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误：{e}")
