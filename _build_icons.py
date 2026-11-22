# -*- coding: utf-8 -*-
"""Genera le icone neon dell'addon (256x256) in resources/icons."""

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 512
PAD = 26
RADIUS = 100
CYAN = (62, 242, 208)
MAGENTA = (192, 75, 240)


def gradient():
    img = Image.new('RGBA', (S, S))
    px = img.load()
    for x in range(S):
        t = x / float(S - 1)
        r = int(CYAN[0] + (MAGENTA[0] - CYAN[0]) * t)
        g = int(CYAN[1] + (MAGENTA[1] - CYAN[1]) * t)
        b = int(CYAN[2] + (MAGENTA[2] - CYAN[2]) * t)
        for y in range(S):
            px[x, y] = (r, g, b, 255)
    return img


GRAD = gradient()


def background():
    """Quadrato scuro arrotondato, con un alone in alto a sinistra."""
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([PAD, PAD, S - PAD, S - PAD], radius=RADIUS,
                           fill=(12, 15, 21, 255))
    haze = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    hd.ellipse([-60, -80, 300, 260], fill=(62, 242, 208, 26))
    hd.ellipse([250, 300, 600, 640], fill=(192, 75, 240, 22))
    haze = haze.filter(ImageFilter.GaussianBlur(70))
    img = Image.alpha_composite(img, haze)
    # bordo sottile neon
    border = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([PAD, PAD, S - PAD, S - PAD], radius=RADIUS,
                         outline=(255, 255, 255, 26), width=3)
    return Image.alpha_composite(img, border)


def finish(mask):
    out = background()
    halo = mask.filter(ImageFilter.GaussianBlur(18))
    halo = halo.point(lambda v: int(v * 0.65))
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    layer.paste(GRAD, (0, 0), halo)
    out = Image.alpha_composite(out, layer)
    solid = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    solid.paste(GRAD, (0, 0), mask)
    return Image.alpha_composite(out, solid)


def base_mask():
    return Image.new('L', (S, S), 0)


def icon_archive():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.line([(112, 246), (256, 148), (400, 246)], fill=255, width=26, joint='curve')
    d.line([(136, 300), (376, 300)], fill=255, width=26)
    for x in (166, 241, 316):
        d.line([(x, 330), (x, 392)], fill=255, width=26)
    d.line([(136, 392), (376, 392)], fill=255, width=26)
    return m


def icon_youtube():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([112, 172, 400, 340], radius=56, outline=255, width=26)
    d.polygon([(228, 216), (228, 296), (310, 256)], fill=255)
    return m


def icon_lists():
    m = base_mask()
    d = ImageDraw.Draw(m)
    for y in (186, 256, 326):
        d.ellipse([146, y - 14, 174, y + 14], fill=255)
        d.line([(206, y), (366, y)], fill=255, width=26)
    return m


def icon_load():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.line([(256, 136), (256, 292)], fill=255, width=26)
    d.line([(194, 238), (256, 300), (318, 238)], fill=255, width=26, joint='curve')
    d.line([(146, 330), (146, 386), (366, 386), (366, 330)], fill=255, width=26, joint='curve')
    return m


def icon_local():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([130, 206, 382, 372], radius=26, outline=255, width=26)
    d.line([(130, 206), (130, 178), (232, 178), (262, 206)], fill=255, width=26, joint='curve')
    return m


def icon_search():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.ellipse([130, 130, 330, 330], outline=255, width=26)
    d.line([(312, 312), (386, 386)], fill=255, width=30)
    return m


def icon_tv():
    m = base_mask()
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([112, 150, 400, 330], radius=30, outline=255, width=26)
    d.line([(256, 330), (256, 366)], fill=255, width=24)
    d.line([(196, 386), (316, 386)], fill=255, width=24)
    return m


def icon_star():
    import math
    m = base_mask()
    d = ImageDraw.Draw(m)
    cx, cy, outer, inner = 256, 262, 128, 54
    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    d.polygon(points, outline=255)
    d.line(points + [points[0]], fill=255, width=22, joint='curve')
    return m


ICONS = [
    ('archive', 'Internet Archive', icon_archive),
    ('youtube', 'YouTube', icon_youtube),
    ('lists', 'Liste', icon_lists),
    ('load', 'Carica link', icon_load),
    ('local', 'Raccolta', icon_local),
    ('search', 'Cerca', icon_search),
    ('tv', 'TV in chiaro', icon_tv),
    ('favorites', 'La mia lista', icon_star),
]


def font(size):
    for name in ('segoeuib.ttf', 'segoeui.ttf'):
        path = os.path.join('C:\\Windows\\Fonts', name)
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def sheet(images, path):
    cell = 230
    gap = 26
    cols = 4
    rows = 2
    width = gap + cols * (cell + gap)
    height = gap + rows * (cell + 76)
    out = Image.new('RGB', (width, height), (7, 9, 12))
    draw = ImageDraw.Draw(out)
    label_font = font(24)
    for index, (name, text, image) in enumerate(images):
        col = index % cols
        row = index // cols
        x = gap + col * (cell + gap)
        y = gap + row * (cell + 76)
        out.paste(image.resize((cell, cell), Image.LANCZOS), (x, y),
                  image.resize((cell, cell), Image.LANCZOS))
        tw = draw.textlength(text, font=label_font)
        draw.text((x + (cell - tw) / 2, y + cell + 18), text,
                  font=label_font, fill=(210, 216, 226))
    out.save(path)
    print('anteprima:', path, out.size)


if __name__ == '__main__':
    target = os.path.join('plugin.video.ghoststream', 'resources', 'icons')
    os.makedirs(target, exist_ok=True)
    for name, text, func in ICONS:
        image = finish(func()).resize((256, 256), Image.LANCZOS)
        image.save(os.path.join(target, name + '.png'))
        print('icona:', name)
    print('fatte', len(ICONS), 'icone in', target)
