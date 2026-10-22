"""
One small image instead of many full-size ones (21 October 2026: reviewing a change meant reading several 1920x1080 shots).
Puts shots, or crops of them, side by side with a short label each, in a sheet at most 1600 px wide.

Usage: py -3 tools/Board.py OUT.png ITEM [ITEM ...]
  ITEM = SHOT[@x0,y0,x1,y1][=label]
  SHOT = a path, or scenario/name under Builds/Shots (".png" may be left out): u16_showroom/v_house_eave_corner
Example: py -3 tools/Board.py Builds/Shots/board.png u16_showroom/v_house_eave_corner@700,300,1500,800=eave u16_showroom/v_swing_wrap
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WIDTH, COLUMNS, LABEL = 1600, 3, 26


def load(item):
    label = None
    if "=" in item:
        item, label = item.split("=", 1)
    crop = None
    if "@" in item:
        item, box = item.split("@", 1)
        crop = tuple(int(v) for v in box.split(","))
    path = item if os.path.isabs(item) or os.path.exists(item) else os.path.join(ROOT, "Builds", "Shots", item)
    if not path.lower().endswith(".png") and not os.path.exists(path):
        path += ".png"
    image = Image.open(path).convert("RGB")
    if crop:
        image = image.crop(crop)
    return image, label or os.path.splitext(os.path.basename(path))[0]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    out, items = argv[1], [load(i) for i in argv[2:]]
    columns = min(COLUMNS, len(items))
    tile_w = (WIDTH - 10 * (columns + 1)) // columns
    tile_h = max(int(tile_w * im.height / im.width) for im, _ in items)
    tile_h = min(tile_h, tile_w)
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (10 + columns * (tile_w + 10), 10 + rows * (tile_h + LABEL + 10)), (30, 30, 34))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for k, (image, label) in enumerate(items):
        x = 10 + (k % columns) * (tile_w + 10)
        y = 10 + (k // columns) * (tile_h + LABEL + 10)
        draw.text((x, y), label, font=font, fill=(235, 235, 235))
        scale = min(tile_w / image.width, tile_h / image.height)
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.LANCZOS)
        sheet.paste(image, (x, y + LABEL))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print(f"{out} ({sheet.width}x{sheet.height}, {len(items)} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
