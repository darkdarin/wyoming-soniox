"""Draw the Wyoming Soniox icon and logos (rendered at 4x, then downsampled).

Usage: uv run --with pillow python scripts/draw_logos.py OUT_DIR
(macOS: uses Arial from the system fonts.)
Writes icon.png and logo.png (the app) and brand_logo.png, brand_dark_logo.png (README, assets/).
"""

import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 4
OUT = sys.argv[1]
NAVY_TOP, NAVY_BOTTOM = (34, 30, 84), (18, 16, 52)
CYAN, VIOLET = (34, 220, 230), (178, 92, 255)
BARS = [0.30, 0.52, 0.78, 1.0, 0.70, 0.46, 0.26]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def badge(size):
    """Rounded square with a gradient border and a sound wave."""
    n = size * S
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    # background gradient
    bg = Image.new("RGBA", (n, n))
    for y in range(n):
        ImageDraw.Draw(bg).line([(0, y), (n, y)], fill=lerp(NAVY_TOP, NAVY_BOTTOM, y / n) + (255,))
    border = Image.new("RGBA", (n, n))
    for x in range(n):
        ImageDraw.Draw(border).line([(x, 0), (x, n)], fill=lerp(CYAN, VIOLET, x / n) + (255,))
    r = int(n * 0.22)
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1], r, fill=255)
    img.paste(border, (0, 0), mask)
    inset = max(int(n * 0.035), 2)
    inner = Image.new("L", (n, n), 0)
    ImageDraw.Draw(inner).rounded_rectangle(
        [inset, inset, n - 1 - inset, n - 1 - inset], r - inset, fill=255
    )
    img.paste(bg, (0, 0), inner)
    # sound wave bars with a soft glow
    bars = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(bars)
    count = len(BARS)
    span = n * 0.62
    w = span / (count * 1.75)
    gap = (span - w * count) / (count - 1)
    x0 = (n - span) / 2
    cy = n / 2
    for i, h in enumerate(BARS):
        x = x0 + i * (w + gap)
        hh = n * 0.58 * h / 2
        color = lerp(CYAN, VIOLET, i / (count - 1)) + (255,)
        d.rounded_rectangle([x, cy - hh, x + w, cy + hh], w / 2, fill=color)
    glow = bars.filter(ImageFilter.GaussianBlur(n * 0.025))
    img.alpha_composite(glow)
    img.alpha_composite(bars)
    return img


def font(size, bold):
    path = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf"
    )
    return ImageFont.truetype(path, size)


def logo(height, dark):
    n_h = height * S
    size = int(n_h * 0.33)
    tx = int(n_h * 1.12)
    text_w = max(font(size, True).getlength("Wyoming"), font(size, False).getlength("Soniox"))
    n_w = int(tx + text_w + n_h * 0.06)
    width = n_w // S
    n_w = width * S
    img = Image.new("RGBA", (n_w, n_h), (0, 0, 0, 0))
    b = badge(height).resize((n_h, n_h), Image.LANCZOS)
    img.alpha_composite(b, (0, 0))
    d = ImageDraw.Draw(img)
    title = (236, 238, 255) if dark else (30, 36, 72)
    sub = (150, 160, 240) if dark else (86, 96, 180)
    d.text((tx, int(n_h * 0.12)), "Wyoming", font=font(size, True), fill=title)
    d.text((tx, int(n_h * 0.52)), "Soniox", font=font(size, False), fill=sub)
    return img.resize((width, height), Image.LANCZOS)


badge(128).resize((128, 128), Image.LANCZOS).save(f"{OUT}/icon.png")
logo(100, dark=False).save(f"{OUT}/logo.png")
logo(256, dark=False).save(f"{OUT}/brand_logo.png")
logo(256, dark=True).save(f"{OUT}/brand_dark_logo.png")
print("ok")
