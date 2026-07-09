#!/usr/bin/env python3
"""デモ用のダミー商品画像を生成する(実運用では楽天の商品画像を使う)。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
ITEMS = [
    ("images/item1.jpg", "電気圧力鍋", (214, 108, 78)),
    ("images/item2.jpg", "ワイヤレスイヤホン", (86, 130, 189)),
    ("images/item3.jpg", "珪藻土バスマット", (118, 160, 120)),
]

base = Path(__file__).parent
(base / "images").mkdir(exist_ok=True)
for name, label, color in ITEMS:
    img = Image.new("RGB", (800, 800), color)
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 760, 760), outline=(255, 255, 255), width=6)
    f = ImageFont.truetype(FONT, 72)
    w = f.getlength(label)
    d.text(((800 - w) / 2, 340), label, font=f, fill=(255, 255, 255))
    d.text((60, 680), "サンプル画像", font=ImageFont.truetype(FONT, 40),
           fill=(255, 255, 255))
    img.save(base / name, quality=90)
    print("generated:", base / name)
