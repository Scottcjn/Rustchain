#!/usr/bin/env python3
"""
Generate placeholder PNG icons from SVG for the BoTTube Chrome Extension.
This script creates simple colored square icons as placeholders.
Requires: Pillow (pip install Pillow)
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size: int, output_path: str):
    """Create a simple gradient icon placeholder."""
    # Create image with gradient background
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient (purple to cyan)
    for y in range(size):
        r = int(139 + (6 - 139) * y / size)  # 8b to 06
        g = int(92 + (182 - 92) * y / size)  # 5c to b6
        b = int(246 + (212 - 246) * y / size)  # f6 to d4
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    # Draw crab emoji (or placeholder text)
    try:
        # Try to use system emoji font
        font_size = int(size * 0.6)
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", font_size)
        except:
            # Fallback: draw text
            font = ImageFont.load_default()
    
    # Draw emoji centered
    emoji = "🦀"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), emoji, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), emoji, font=font)
    
    # Save
    img.save(output_path, 'PNG')
    print(f"Created: {output_path} ({size}x{size})")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(script_dir, 'extension', 'icons')
    
    os.makedirs(icons_dir, exist_ok=True)
    
    sizes = [16, 48, 128]
    for size in sizes:
        output_path = os.path.join(icons_dir, f'icon{size}.png')
        create_icon(size, output_path)
    
    print("\nIcons generated successfully!")
    print("Note: These are placeholder icons. Replace with designed icons for production.")

if __name__ == '__main__':
    main()
