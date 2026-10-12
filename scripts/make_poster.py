#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把生图出的主视觉合成成宣传海报 + GitHub OG 横幅。

两步法：生图负责视觉，本脚本负责叠中文字幕（AI 直接出中文会糊）。

⚠️ Pillow 坑：在 RGB 画布上传 (r,g,b,a) 四元组，alpha 会被原样写进像素，
   随后 convert("RGB") 丢 alpha 就变成实心色块。半透明元素必须画在独立的
   透明 chrome 层上，最后 alpha_composite 合成。
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "screenshots")
SRC = os.path.join(SHOTS, "Premium_3D_product_marketing_i_2026-10-12T13-56-40.png")

F_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
F_REG = "C:/Windows/Fonts/msyh.ttc"
F_NUM = "C:/Windows/Fonts/arialbd.ttf"

RED = (218, 41, 28)
YEL = (255, 199, 44)
WHITE = (255, 255, 255)
GRAY = (154, 164, 191)
DIM = (108, 118, 148)

# 半透明色（只能画在 chrome 层上）
GLASS = (255, 255, 255, 16)
EDGE = (255, 255, 255, 52)
HAIR = (255, 255, 255, 26)


def font(path, size):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------- 去水印
def strip_watermark(im: Image.Image) -> Image.Image:
    """右下角平台水印用左侧同排邻域像素平移补齐（该区域是平滑渐变）。"""
    x0, y0, x1, y1 = 856, 926, 1024, 1014
    shift = 172
    patch = im.crop((x0 - shift, y0, x0 - shift + (x1 - x0), y1))
    feather = 34
    for i in range(feather):
        a = i / float(feather)
        xs = x0 + i
        col_old = im.crop((xs, y0, xs + 1, y1))
        col_new = patch.crop((i, 0, i + 1, patch.height))
        im.paste(Image.blend(col_old, col_new, a), (xs, y0))
    im.paste(patch.crop((feather, 0, patch.width, patch.height)), (x0 + feather, y0))
    seam = im.crop((x0 - 6, y0, x0 + 40, y1)).filter(ImageFilter.GaussianBlur(3))
    im.paste(seam, (x0 - 6, y0))
    return im


# ---------------------------------------------------------------- 画布
def new_canvas(w, h, glow_cy):
    """返回 (base, chrome, out)。base=不透明底；chrome=透明层，半透明元素画这里。"""
    base = Image.new("RGB", (w, h), (11, 16, 32))
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / float(h)
        d.line([(0, y), (w, y)], fill=(int(11 + 10 * t), int(16 + 12 * t), int(32 + 22 * t)))

    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, w + 1, 60):
        gd.line([(x, 0), (x, h)], fill=(255, 255, 255, 9), width=1)
    for y in range(0, h + 1, 60):
        gd.line([(0, y), (w, y)], fill=(255, 255, 255, 9), width=1)
    base = Image.alpha_composite(base.convert("RGBA"), grid).convert("RGB")

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [w // 2 - 520, glow_cy - 380, w // 2 + 520, glow_cy + 380], fill=(218, 41, 28, 70)
    )
    base = Image.alpha_composite(
        base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(150))
    ).convert("RGB")

    chrome = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return base, chrome


def finish(base, chrome):
    return Image.alpha_composite(base.convert("RGBA"), chrome).convert("RGB")


def paste_round(canvas, img, box, radius):
    x, y, w, h = box
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    canvas.paste(img, (x, y), mask)


def pill(d, xy, text, f, fg, bg, pad_x=26, h=54):
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + pad_x * 2, y + h], radius=h // 2, fill=bg)
    d.text((x + pad_x, y + h // 2), text, font=f, fill=fg, anchor="lm")
    return tw + pad_x * 2


def url_chip(d, cx, cy, url, f):
    """居中放置仓库地址胶囊，返回左右边界。"""
    uw = d.textlength(url, font=f)
    w = uw + 96
    x0, y0 = cx - w / 2, cy - 28
    d.rounded_rectangle([x0, y0, x0 + w, y0 + 56], radius=28, fill=GLASS, outline=EDGE, width=2)
    d.ellipse([x0 + 26, y0 + 19, x0 + 50, y0 + 43], fill=YEL)
    d.text((x0 + 66, cy), url, font=f, fill=WHITE, anchor="lm")


# ---------------------------------------------------------------- 竖版海报
def build_poster(hero):
    W, H = 1080, 1600
    M = 80
    base, chrome = new_canvas(W, H, glow_cy=880)
    d = ImageDraw.Draw(chrome)

    f_brand = font(F_BOLD, 26)
    f_title = font(F_BOLD, 96)
    f_sub = font(F_REG, 44)
    f_num = font(F_NUM, 54)
    f_lab = font(F_REG, 23)
    f_url = font(F_BOLD, 30)

    # 主视觉卡片（不透明图先贴到底图）
    card = (M, 470, W - M * 2, 900)
    paste_round(base, hero.resize((card[2], card[3]), Image.LANCZOS), card, 40)
    d.rounded_rectangle([card[0], card[1], card[0] + card[2] - 1, card[1] + card[3] - 1],
                        radius=40, outline=EDGE, width=2)

    # 顶部品牌条
    pill(d, (M, 82), "麦当劳 MCP  ·  AI Skill", f_brand, WHITE, RED)

    # 主标题 / 副标题
    d.text((M - 4, 268), "麦麦体检报告", font=f_title, fill=WHITE)
    d.text((M, 384), "吃麦当劳，也能做体检", font=f_sub, fill=YEL)

    # 数据条
    stats = [("160", "官方营养数据"), ("10", "只读 MCP 工具"),
             ("100%", "商品名匹配率"), ("0", "第三方依赖")]
    sy = 1420
    colw = (W - M * 2) / 4.0
    for i, (num, lab) in enumerate(stats):
        cx = M + colw * i + colw / 2
        d.text((cx, sy), num, font=f_num, fill=YEL, anchor="mm")
        d.text((cx, sy + 52), lab, font=f_lab, fill=GRAY, anchor="mm")
        if i:
            d.line([(M + colw * i, sy - 14), (M + colw * i, sy + 56)], fill=HAIR, width=1)

    url_chip(d, W / 2, 1532, "github.com/LeeX852/mcd-checkup", f_url)

    out = os.path.join(SHOTS, "poster.png")
    finish(base, chrome).save(out, "PNG")
    return out


# ---------------------------------------------------------------- OG 横幅
def build_og(hero):
    W, H = 1200, 630
    base, chrome = new_canvas(W, H, glow_cy=H // 2)
    d = ImageDraw.Draw(chrome)

    f_brand = font(F_BOLD, 22)
    f_title = font(F_BOLD, 68)
    f_sub = font(F_REG, 30)
    f_url = font(F_BOLD, 26)
    f_note = font(F_REG, 20)

    # 右侧主视觉（取方形图中段，避开顶部空白与底部水印带）
    crop = hero.crop((120, 90, 904, 874)).resize((500, 500), Image.LANCZOS)
    paste_round(base, crop, (660, 65, 500, 500), 32)
    d.rounded_rectangle([660, 65, 1159, 564], radius=32, outline=EDGE, width=2)

    pill(d, (60, 78), "麦当劳 MCP  ·  AI Skill", f_brand, WHITE, RED, pad_x=20, h=44)
    d.text((56, 240), "麦麦体检报告", font=f_title, fill=WHITE)
    d.text((60, 336), "吃麦当劳，也能做体检", font=f_sub, fill=YEL)
    d.text((60, 392), "历史订单 × 餐品营养 × 积分 × 优惠券 交叉分析", font=f_note, fill=GRAY)
    d.text((60, 560), "麦当劳 Skill 开发大赛 · 参赛作品", font=f_note, fill=DIM)

    url_chip(d, 300, 499, "github.com/LeeX852/mcd-checkup", f_url)

    out = os.path.join(SHOTS, "og-banner.png")
    finish(base, chrome).save(out, "PNG")
    return out


def main():
    hero = strip_watermark(Image.open(SRC).convert("RGB"))
    hero_path = os.path.join(SHOTS, "hero-clean.png")
    hero.save(hero_path, "PNG")
    for f in (hero_path, build_poster(hero), build_og(hero)):
        print(os.path.getsize(f), f)


if __name__ == "__main__":
    main()
