#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v1")
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"

W, H = 1080, 1350
PAD = 72
CONTENT_W = W - PAD * 2
HEADER_TOP = 8
HEADER_H = 102
CONTENT_TOP = HEADER_TOP + HEADER_H + 24
FOOTER_H = 72
CONTENT_BOTTOM = H - FOOTER_H - 32

BG = "#F7F5F2"
CORAL = "#D97D55"
PRIMARY = "#1A1A1A"
SECONDARY = "#6B6B6B"
DIVIDER = "#D8D4CE"
TOTAL = 8
SZ_HEADER = 42
SZ_BODY = 34


def font(size, bold=False):
    idx = 0 if bold else 1
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def is_cjk(c):
    cp = ord(c)
    return 0x4E00 <= cp <= 0x9FFF or 0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF or 0x3400 <= cp <= 0x4DBF


def wrap(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        tokens, i = [], 0
        while i < len(para):
            c = para[i]
            if is_cjk(c) or c in "「」，。！？、：；''\"\"…—·×→%+/·（）()":
                tokens.append(c); i += 1
            elif c == " ":
                tokens.append(" "); i += 1
            else:
                j = i
                while j < len(para) and not is_cjk(para[j]) and para[j] != " ":
                    j += 1
                tokens.append(para[i:j]); i = j
        cur = ""
        for tok in tokens:
            test = cur + tok
            bx = draw.textbbox((0, 0), test, font=fnt)
            if bx[2] - bx[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur.strip())
                cur = ""
                for ch in tok:
                    t2 = cur + ch
                    b2 = draw.textbbox((0, 0), t2, font=fnt)
                    if b2[2] - b2[0] <= max_w:
                        cur = t2
                    else:
                        lines.append(cur.strip()); cur = ch
        if cur.strip():
            lines.append(cur.strip())
    return lines


def text_block(draw, text, x, y, fnt, color, max_w, ls=1.52):
    lh = int(fnt.size * ls)
    for line in wrap(draw, text, fnt, max_w):
        if line.strip():
            draw.text((x, y), line, font=fnt, fill=color)
        y += lh
    return y


def draw_chrome(draw, card_n, series="200亿 Token 实验"):
    draw.rectangle([0, 0, W, HEADER_TOP], fill=CORAL)
    fy = HEADER_TOP + 18
    draw.text((PAD, fy), series, font=font(24), fill=CORAL)
    num_str = f"{card_n:02d}  /  {TOTAL:02d}"
    nb = draw.textbbox((0, 0), num_str, font=font(22, bold=True))
    draw.text((W - PAD - (nb[2] - nb[0]), fy + 2), num_str, font=font(22, bold=True), fill=SECONDARY)
    draw.line([(PAD, HEADER_TOP + HEADER_H), (W - PAD, HEADER_TOP + HEADER_H)], fill=DIVIDER, width=1)
    draw.line([(PAD, CONTENT_BOTTOM + 16), (W - PAD, CONTENT_BOTTOM + 16)], fill=DIVIDER, width=1)
    draw.text((PAD, CONTENT_BOTTOM + 28), "Terry Chen  ·  chenterry.com", font=font(20), fill=SECONDARY)


def new_card():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def section_header(draw, text, y):
    fnt = font(SZ_HEADER, bold=True)
    bar_h = int(SZ_HEADER * 1.25)
    draw.rectangle([PAD, y, PAD + 6, y + bar_h], fill=CORAL)
    draw.text((PAD + 20, y + 2), text, font=fnt, fill=PRIMARY)
    return y + bar_h + 22


def save_card(i, lines, title):
    img, draw = new_card()
    draw_chrome(draw, i)
    y = CONTENT_TOP
    y = section_header(draw, title, y)
    fb = font(SZ_BODY)
    for p in lines:
        y = text_block(draw, p, PAD, y, fb, PRIMARY, CONTENT_W)
        y += 18
    img.save(os.path.join(OUT_DIR, f"card_{i:02d}.png"))
    print(f"card_{i:02d}.png ✓")


def make_cover():
    img, draw = new_card()
    draw_chrome(draw, 1)
    y = CONTENT_TOP + 120
    draw.text((PAD, y), "一个月烧完 200 亿 AI Token", font=font(64, bold=True), fill=PRIMARY)
    y += 95
    draw.text((PAD, y), "能做出什么样的产品？", font=font(64, bold=True), fill=CORAL)
    y += 130
    draw.text((PAD, y), "这不是烧钱挑战，而是一次产品形态实验。", font=font(36), fill=SECONDARY)
    y += 90
    stats = [("200亿", "Token"), ("30", "天"), ("2", "核心问题")]
    col_w = CONTENT_W // 3
    for idx, (n, lab) in enumerate(stats):
        x = PAD + idx * col_w
        draw.text((x, y), n, font=font(56, bold=True), fill=PRIMARY)
        draw.text((x, y + 80), lab, font=font(28), fill=SECONDARY)
    img.save(os.path.join(OUT_DIR, "card_01.png"))
    print("card_01.png ✓")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    make_cover()
    save_card(2, ["我想回答两个问题：", "第一，AI 除了写代码，还应该怎样接管运营任务？", "第二，AI 能做出的“最有价值产品”到底长什么样？", "如果生产主体从人变成 Agent，产品逻辑会被整体改写。"], "实验问题")
    save_card(3, ["先看广告。", "如果未来主要“消费信息”的是 Agent，而不是人，", "广告就不再是给人看的创意竞争，", "而会变成给 Agent 读取、比较、决策的结构化接口。"], "产品形态变化（1）")
    save_card(4, ["再看界面。", "多模态 Agent + 手机侧 Agent 出现后，", "大量任务可以直接由 Agent 执行。", "这时复杂 GUI 可能不是优势，而是额外负担。"], "产品形态变化（2）")
    save_card(5, ["工具层已经有信号：", "数据库、后端、邮件这些标准化能力，", "正在变成 Agent 默认可调用的基础设施。", "Supabase、Resend 这类服务，就是典型例子。"], "基础设施变化")
    save_card(6, ["很多“为人设计”的产品，可能要重做一遍。", "比如 Yelp、比如大量 SaaS。", "今天的信息结构围绕“人怎么理解和操作”，", "明天可能要围绕“Agent 怎么读取和执行”。"], "重做一遍产品")
    save_card(7, ["我更在意的，是组织层竞争力变化。", "未来比的可能不再只是人效，", "而是 Token ROI：", "同样 1000 token，谁能换来真实功能、增长和收入。"], "Token ROI")
    save_card(8, ["所以这次实验的本质是：", "不再刻意省 token，而是放大计算，", "让 Agent 处理更多不确定性，", "看产品会不会走向完全不同的形态。", "如果 AI 成本趋近于零，你会怎么设计你的产品？"], "接下来一个月")
    print(f"\n✅ Done. Output -> {OUT_DIR}")


if __name__ == "__main__":
    main()
