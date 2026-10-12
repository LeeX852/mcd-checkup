#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按平台规格生成宣传图。

小红书图文首图 3:4（1080x1440），抖音图文/视频封面 9:16（1080x1920）。
复用 make_poster 的画布与叠字基建（半透明元素必须走独立 chrome 层）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw  # noqa: E402

from make_poster import (  # noqa: E402
    F_BOLD, F_NUM, F_REG, GRAY, DIM, YEL, WHITE,
    SHOTS, finish, font, new_canvas, paste_round, pill, strip_watermark, url_chip,
)

HERO = os.path.join(SHOTS, "Premium_3D_product_marketing_i_2026-10-12T13-56-40.png")

STATS = [("160", "官方营养数据"), ("10", "只读 MCP 工具"),
         ("100%", "商品名匹配率"), ("0", "第三方依赖")]


def header(d, W, M, f_brand, f_title, f_sub, title, sub):
    pill(d, (M, 72), "麦当劳 MCP  ·  AI Skill", f_brand, WHITE, (218, 41, 28),
         pad_x=24, h=52)
    d.text((M - 4, 172), title, font=f_title, fill=WHITE)
    d.text((M, 300), sub, font=f_sub, fill=YEL)


def stat_row(d, M, W, y, f_num, f_lab, cols=4):
    colw = (W - M * 2) / float(cols)
    for i, (num, lab) in enumerate(STATS):
        cx = M + colw * i + colw / 2
        d.text((cx, y), num, font=f_num, fill=YEL, anchor="mm")
        d.text((cx, y + 50), lab, font=f_lab, fill=GRAY, anchor="mm")
        if i:
            d.line([(M + colw * i, y - 14), (M + colw * i, y + 54)],
                   fill=(255, 255, 255, 26), width=1)


# ---------------------------------------------------------------- 小红书 3:4
def build_xhs(hero):
    W, H, M = 1080, 1440, 72
    base, chrome = new_canvas(W, H, glow_cy=760)
    d = ImageDraw.Draw(chrome)

    f_brand = font(F_BOLD, 24)
    f_title = font(F_BOLD, 86)
    f_sub = font(F_REG, 40)
    f_num = font(F_NUM, 48)
    f_lab = font(F_REG, 22)
    f_url = font(F_BOLD, 28)
    f_note = font(F_REG, 21)

    box = (180, 386, 720, 720)
    paste_round(base, hero.resize((box[2], box[3]), Image.LANCZOS), box, 36)
    d.rounded_rectangle([box[0], box[1], box[0] + box[2] - 1, box[1] + box[3] - 1],
                        radius=36, outline=(255, 255, 255, 52), width=2)

    header(d, W, M, f_brand, f_title, f_sub, "麦麦体检报告", "吃麦当劳，也能做体检")
    stat_row(d, M, W, 1150, f_num, f_lab)
    url_chip(d, W / 2, 1296, "github.com/LeeX852/mcd-checkup", f_url)
    d.text((W / 2, 1382), "麦当劳 Skill 开发大赛 · 参赛作品", font=f_note, fill=DIM,
           anchor="mm")

    out = os.path.join(SHOTS, "xhs-cover.png")
    finish(base, chrome).save(out, "PNG")
    return out


# ---------------------------------------------------------------- 抖音 9:16
def build_dy(hero):
    W, H, M = 1080, 1920, 80
    base, chrome = new_canvas(W, H, glow_cy=900)
    d = ImageDraw.Draw(chrome)

    f_brand = font(F_BOLD, 26)
    f_title = font(F_BOLD, 96)
    f_sub = font(F_REG, 42)
    f_num = font(F_NUM, 60)
    f_lab = font(F_REG, 25)
    f_url = font(F_BOLD, 30)
    f_note = font(F_REG, 22)

    box = (M, 452, W - M * 2, 880)
    paste_round(base, hero.resize((box[2], box[3]), Image.LANCZOS), box, 40)
    d.rounded_rectangle([box[0], box[1], box[0] + box[2] - 1, box[1] + box[3] - 1],
                        radius=40, outline=(255, 255, 255, 52), width=2)

    header(d, W, M, f_brand, f_title, f_sub, "麦麦体检报告", "吃麦当劳，也能做体检")

    # 2x2 数据网格
    gx, gy = M, 1396
    cw, ch = (W - M * 2) / 2.0, 118
    for i, (num, lab) in enumerate(STATS):
        cx = gx + cw * (i % 2) + cw / 2
        cy = gy + ch * (i // 2) + ch / 2
        d.text((cx - 44, cy), num, font=f_num, fill=YEL, anchor="rm")
        d.text((cx - 24, cy + 4), lab, font=f_lab, fill=GRAY, anchor="lm")

    url_chip(d, W / 2, 1706, "github.com/LeeX852/mcd-checkup", f_url)
    d.text((W / 2, 1810), "麦当劳 Skill 开发大赛 · 参赛作品", font=f_note, fill=DIM,
           anchor="mm")

    out = os.path.join(SHOTS, "dy-cover.png")
    finish(base, chrome).save(out, "PNG")
    return out


# ---------------------------------------------------------------- 报告内页
REPORT = os.path.join(SHOTS, "report.png")


def _pad_to(canvas_w, canvas_h, img, bg=(13, 19, 36)):
    """把图等比缩放后居中贴到深色画布上（抖音图文要 9:16，报告截图是 3:4）。"""
    scale = min(canvas_w / img.width, canvas_h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    out = Image.new("RGB", (canvas_w, canvas_h), bg)
    out.paste(img, ((canvas_w - img.width) // 2, (canvas_h - img.height) // 2))
    return out


def build_inner_pages():
    """从报告截图裁两段：小红书直接出 3:4，抖音补边成 9:16。"""
    report = Image.open(REPORT).convert("RGB")
    crops = [(160, 0), (160, 720)]
    made = []
    for i, (x0, y0) in enumerate(crops, start=2):
        seg = report.crop((x0, y0, x0 + 960, y0 + 1280))
        xhs = seg.resize((1080, 1440), Image.LANCZOS)
        p = os.path.join(SHOTS, "xhs-p%d.png" % i)
        xhs.save(p, "PNG")
        made.append(p)

        dy = _pad_to(1080, 1920, seg)
        p = os.path.join(SHOTS, "dy-p%d.png" % i)
        dy.save(p, "PNG")
        made.append(p)
    return made


def main():
    hero = strip_watermark(Image.open(HERO).convert("RGB"))
    made = [build_xhs(hero), build_dy(hero)] + build_inner_pages()
    for f in made:
        print(os.path.getsize(f), f)


if __name__ == "__main__":
    main()
