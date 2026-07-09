#!/usr/bin/env python3
"""楽天アフィ商品紹介ショート動画メーカー.

商品情報(JSON)から、縦型1080x1920のランキング形式ショート動画と
投稿用キャプションを自動生成する。

使い方:
    python3 make_video.py products.json -o output/

必要なもの: Python 3.9+, Pillow, ffmpeg, 日本語フォント
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
FPS = 30

# 配色
BG_TOP = (16, 20, 32)
BG_BOTTOM = (30, 38, 60)
ACCENT = (255, 197, 61)      # 金色: 順位・価格
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (200, 205, 215)
CARD_BG = (255, 255, 255)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    sys.exit("日本語フォントが見つかりません。FONT_CANDIDATES にパスを追加してください。")


FONT_PATH = find_font()


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def wrap_text(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """日本語向けに1文字単位で折り返す。"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if fnt.getlength(cur + ch) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return [l for l in lines if l]


def draw_centered(draw: ImageDraw.ImageDraw, y: int, text: str,
                  fnt: ImageFont.FreeTypeFont, fill, stroke_width: int = 0,
                  stroke_fill=None) -> int:
    """中央揃えで1行描画し、次の行のy座標を返す。"""
    w = fnt.getlength(text)
    draw.text(((W - w) / 2, y), text, font=fnt, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill)
    ascent, descent = fnt.getmetrics()
    return y + ascent + descent


def base_canvas() -> Image.Image:
    """上下グラデーションの背景を作る。"""
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), tuple(
            round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    return grad.resize((W, H))


def add_pr_badge(img: Image.Image) -> None:
    """左上にPR表記(ステマ規制対応)。全スライド必須。"""
    draw = ImageDraw.Draw(img)
    f = font(40)
    pad = 18
    tw = f.getlength("PR")
    x0, y0 = 40, 60
    draw.rounded_rectangle(
        (x0, y0, x0 + tw + pad * 2, y0 + 40 + pad * 2),
        radius=14, outline=TEXT_SUB, width=3)
    draw.text((x0 + pad, y0 + pad - 4), "PR", font=f, fill=TEXT_SUB)


def load_product_image(src: str, base_dir: Path) -> Image.Image:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
        tmp.write(data)
        tmp.close()
        return Image.open(tmp.name).convert("RGB")
    return Image.open(base_dir / src).convert("RGB")


def render_intro(cfg: dict) -> Image.Image:
    img = base_canvas()
    draw = ImageDraw.Draw(img)
    add_pr_badge(img)

    title = cfg["title"]
    f_title = font(88)
    lines = wrap_text(title, f_title, W - 160)
    line_h = sum(f_title.getmetrics()) + 20
    y = (H - line_h * len(lines)) // 2 - 100
    for line in lines:
        y = draw_centered(draw, y, line, f_title, TEXT_MAIN,
                          stroke_width=3, stroke_fill=TEXT_MAIN) + 20

    # アクセントの下線
    bar_w = 400
    draw.rounded_rectangle(((W - bar_w) / 2, y + 30, (W + bar_w) / 2, y + 44),
                           radius=7, fill=ACCENT)

    sub = cfg.get("intro_sub", "最後まで見てね")
    draw_centered(draw, y + 120, sub, font(52), TEXT_SUB)
    return img


def render_product(product: dict, rank: int, base_dir: Path) -> Image.Image:
    img = base_canvas()
    draw = ImageDraw.Draw(img)
    add_pr_badge(img)

    # 順位
    y = 150
    y = draw_centered(draw, y, f"第{rank}位", font(110), ACCENT,
                      stroke_width=4, stroke_fill=ACCENT)

    # 商品画像カード(角丸・影付き)
    card = 880
    cx, cy = (W - card) // 2, y + 50
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (cx + 12, cy + 16, cx + card + 12, cy + card + 16),
        radius=40, fill=(0, 0, 0, 140))
    img.paste(Image.alpha_composite(img.convert("RGBA"), shadow.filter(
        ImageFilter.GaussianBlur(14))).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((cx, cy, cx + card, cy + card), radius=40, fill=CARD_BG)

    photo = load_product_image(product["image"], base_dir)
    photo = ImageOps.contain(photo, (card - 80, card - 80))
    img.paste(photo, (cx + (card - photo.width) // 2,
                      cy + (card - photo.height) // 2))
    draw = ImageDraw.Draw(img)

    # 商品名(最大2行)
    y = cy + card + 60
    f_name = font(62)
    for line in wrap_text(product["name"], f_name, W - 140)[:2]:
        y = draw_centered(draw, y, line, f_name, TEXT_MAIN,
                          stroke_width=2, stroke_fill=TEXT_MAIN) + 8

    # 価格
    if product.get("price"):
        y = draw_centered(draw, y + 24, product["price"], font(80), ACCENT,
                          stroke_width=3, stroke_fill=ACCENT)

    # ひとことコメント(最大2行)
    if product.get("comment"):
        f_com = font(48)
        y += 30
        for line in wrap_text(product["comment"], f_com, W - 160)[:2]:
            y = draw_centered(draw, y, line, f_com, TEXT_SUB) + 6
    return img


def render_outro(cfg: dict) -> Image.Image:
    img = base_canvas()
    draw = ImageDraw.Draw(img)
    add_pr_badge(img)

    cta = cfg.get("cta", "詳細はプロフィールの\n楽天ROOMから")
    f_cta = font(84)
    lines = []
    for part in cta.split("\n"):
        lines.extend(wrap_text(part, f_cta, W - 160))
    line_h = sum(f_cta.getmetrics()) + 24
    y = (H - line_h * len(lines)) // 2 - 120
    for line in lines:
        y = draw_centered(draw, y, line, f_cta, TEXT_MAIN,
                          stroke_width=3, stroke_fill=TEXT_MAIN) + 24

    draw_centered(draw, y + 80, "フォローもうれしいです", font(52), ACCENT)
    draw_centered(draw, H - 220, "※本動画はアフィリエイトリンクを含みます(PR)",
                  font(36), TEXT_SUB)
    return img


def build_ffmpeg_cmd(slides: list[tuple[Path, float]], out: Path,
                     bgm: Path | None, zoom: bool) -> list[str]:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path, dur in slides:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}",
                "-i", str(path)]
    if bgm:
        cmd += ["-i", str(bgm)]

    parts = []
    for i, (_, dur) in enumerate(slides):
        frames = int(dur * FPS)
        chain = f"[{i}:v]"
        if zoom:
            # 一旦拡大してからzoompanするとカクつきが出にくい
            chain += (f"scale={W * 2}:{H * 2}:flags=lanczos,"
                      f"zoompan=z='1+0.05*on/{frames}'"
                      f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d=1:s={W}x{H}:fps={FPS},")
        fade_out = max(dur - 0.25, 0)
        chain += (f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.2f}:d=0.25,"
                  f"setsar=1[v{i}]")
        parts.append(chain)
    concat_in = "".join(f"[v{i}]" for i in range(len(slides)))
    parts.append(f"{concat_in}concat=n={len(slides)}:v=1:a=0[v]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]"]
    if bgm:
        total = sum(d for _, d in slides)
        cmd += ["-map", f"{len(slides)}:a",
                "-af", f"afade=t=out:st={max(total - 1, 0):.2f}:d=1",
                "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", str(out)]
    return cmd


def write_caption(cfg: dict, out_dir: Path) -> Path:
    lines = [cfg["title"], ""]
    for i, p in enumerate(cfg["products"], start=1):
        price = f" {p['price']}" if p.get("price") else ""
        lines.append(f"第{i}位 {p['name']}{price}")
    lines += ["", cfg.get("cta", "詳細はプロフィールの楽天ROOMから").replace("\n", ""),
              "", "※アフィリエイトリンクを含みます"]
    tags = cfg.get("hashtags",
                   ["#PR", "#楽天", "#楽天room", "#楽天購入品", "#買ってよかった"])
    lines.append(" ".join(tags))
    path = out_dir / "caption.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="楽天アフィ紹介ショート動画を生成")
    ap.add_argument("config", help="商品情報JSONのパス")
    ap.add_argument("-o", "--out-dir", default="output", help="出力先ディレクトリ")
    ap.add_argument("--no-zoom", action="store_true", help="ズーム演出を無効化")
    ap.add_argument("--intro-sec", type=float, default=1.8)
    ap.add_argument("--product-sec", type=float, default=3.2)
    ap.add_argument("--outro-sec", type=float, default=2.5)
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg が見つかりません。インストールしてください。")

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base_dir = cfg_path.parent
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    products = cfg["products"]
    slides_img: list[Image.Image] = [render_intro(cfg)]
    # ランキングはカウントダウン(最下位→1位)で見せる
    for idx in range(len(products) - 1, -1, -1):
        slides_img.append(render_product(products[idx], idx + 1, base_dir))
    slides_img.append(render_outro(cfg))

    durations = ([args.intro_sec]
                 + [args.product_sec] * len(products)
                 + [args.outro_sec])

    with tempfile.TemporaryDirectory() as td:
        slides: list[tuple[Path, float]] = []
        for i, (im, dur) in enumerate(zip(slides_img, durations)):
            p = Path(td) / f"slide_{i:02d}.png"
            im.save(p)
            slides.append((p, dur))

        bgm = Path(base_dir / cfg["bgm"]) if cfg.get("bgm") else None
        out_mp4 = out_dir / (cfg.get("output_name") or (cfg_path.stem + ".mp4"))
        cmd = build_ffmpeg_cmd(slides, out_mp4, bgm, zoom=not args.no_zoom)
        subprocess.run(cmd, check=True)

    caption = write_caption(cfg, out_dir)
    total = sum(durations)
    print(f"動画:        {out_mp4}  ({total:.1f}秒, {W}x{H})")
    print(f"キャプション: {caption}")


if __name__ == "__main__":
    main()
