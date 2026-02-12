# Python script to create and update documentation files

import os

def create_wrtc_quickstart():
    try:
        # Create the 'docs' directory if it doesn't exist
        os.makedirs('docs', exist_ok=True)

        # Define the content of the wRTC Quickstart document
        wrtc_content = """
# wRTC Quickstart Guide

## Introduction
Welcome to the wRTC Quickstart Guide. This document will guide you through the process of buying, verifying, and bridging wRTC into BoTTube credits. Follow these steps to ensure a safe and efficient experience.

## Anti-Scam Checklist
- Verify the correct mint address: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`.
- Ensure the token has `6` decimals.
- Do not rely solely on ticker symbols.
- Verify contract addresses on official sites.

## Canonical wRTC Information
- The real wRTC is defined by its mint address and decimals.
- Official links for swaps and bridging will be provided below.

## Step-by-Step Guides

### Buy/Obtain wRTC via Raydium
1. Access Raydium using the official link.
2. Swap SOL to wRTC.
3. Verify the acquired token matches the official mint and decimals.

### Bridge wRTC to BoTTube
1. Use the BoTTube bridge link to transfer wRTC to BoTTube credits.

### Withdraw RTC back to wRTC
1. Follow the guide to withdraw credits back to wRTC.

## Conclusion
Ensure all steps are followed carefully to avoid scams and successfully manage your wRTC and BoTTube credits.

"""

        # Write the content to the 'wrtc.md' file
        with open('docs/wrtc.md', 'w') as file:
            file.write(wrtc_content)

        # Update the main README.md file
        update_readme()

    except Exception as e:
        print(f"An error occurred: {e}")

def update_readme():
    try:
        # Check if README.md exists
        if os.path.exists('README.md'):
            with open('README.md', 'a') as readme:
                readme.write("\n## Documentation\n- [wRTC Quickstart Guide](docs/wrtc.md)\n")
        else:
            with open('README.md', 'w') as readme:
                readme.write("# Project Documentation\n\n## Documentation\n- [wRTC Quickstart Guide](docs/wrtc.md)\n")

    except Exception as e:
        print(f"An error occurred while updating README.md: {e}")

if __name__ == "__main__":
    create_wrtc_quickstart()