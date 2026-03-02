#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "v3_fulltext")
SRC_MD = "/Users/terry/Desktop/crowdlisten_files/crowdlisten_marketing/notes/token_experiment_zh.md"
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"

W, H = 1080, 1350
PAD = 64
CONTENT_W = W - PAD * 2
HEADER_TOP = 8
HEADER_H = 102
CONTENT_TOP = HEADER_TOP + HEADER_H + 24
FOOTER_H = 72
CONTENT_BOTTOM = H - FOOTER_H - 32
CONTENT_H = CONTENT_BOTTOM - CONTENT_TOP

BG = "#F7F5F2"
CORAL = "#D97D55"
PRIMARY = "#1A1A1A"
SECONDARY = "#6B6B6B"
DIVIDER = "#D8D4CE"

SZ_HEADER = 40
SZ_BODY = 35   # bigger
LS = 1.42      # tighter to fill more area with big font
PARA_GAP = 10


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
                        if cur.strip():
                            lines.append(cur.strip())
                        cur = ch
        if cur.strip():
            lines.append(cur.strip())
    return lines


def para_height(draw, text, fnt, max_w, ls=LS):
    lh = int(fnt.size * ls)
    return len(wrap(draw, text, fnt, max_w)) * lh


def draw_text(draw, text, x, y, fnt, color, max_w, ls=LS):
    lh = int(fnt.size * ls)
    for line in wrap(draw, text, fnt, max_w):
        if line.strip():
            draw.text((x, y), line, font=fnt, fill=color)
        y += lh
    return y


def draw_chrome(draw, card_n, total, series="200亿 Token 实验"):
    draw.rectangle([0, 0, W, HEADER_TOP], fill=CORAL)
    fy = HEADER_TOP + 18
    draw.text((PAD, fy), series, font=font(24), fill=CORAL)
    num = f"{card_n:02d}  /  {total:02d}"
    nb = draw.textbbox((0,0), num, font=font(22, bold=True))
    draw.text((W - PAD - (nb[2]-nb[0]), fy+2), num, font=font(22, bold=True), fill=SECONDARY)
    draw.line([(PAD, HEADER_TOP+HEADER_H), (W-PAD, HEADER_TOP+HEADER_H)], fill=DIVIDER, width=1)
    draw.line([(PAD, CONTENT_BOTTOM+16), (W-PAD, CONTENT_BOTTOM+16)], fill=DIVIDER, width=1)
    draw.text((PAD, CONTENT_BOTTOM+28), "Terry Chen  ·  chenterry.com", font=font(20), fill=SECONDARY)


def section_header(draw, title, y):
    fnt = font(SZ_HEADER, bold=True)
    bar_h = int(SZ_HEADER * 1.2)
    draw.rectangle([PAD, y, PAD+6, y+bar_h], fill=CORAL)
    draw.text((PAD+18, y+2), title, font=fnt, fill=PRIMARY)
    return y + bar_h + 18


def load_paragraphs(path):
    text = open(path, "r", encoding="utf-8").read()
    lines = [ln.rstrip() for ln in text.splitlines()]
    paras = []
    buf = []
    for ln in lines:
        if ln.startswith("#"):
            continue
        if ln.strip() == "":
            if buf:
                paras.append("".join(buf).strip())
                buf = []
            continue
        # keep numbered points as standalone lines
        if ln.strip().startswith(("1.", "2.", "（1）", "（2）")):
            if buf:
                paras.append("".join(buf).strip())
                buf = []
            paras.append(ln.strip())
        else:
            buf.append(ln.strip())
    if buf:
        paras.append("".join(buf).strip())
    return [p for p in paras if p]


def paginate(paras):
    dummy = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(dummy)
    fb = font(SZ_BODY)

    pages = []
    cur = []
    used = 0

    # page 2+ available height after section header
    avail = CONTENT_H - int(SZ_HEADER * 1.2) - 24

    for p in paras:
        h = para_height(d, p, fb, CONTENT_W) + PARA_GAP
        if cur and used + h > avail:
            pages.append(cur)
            cur = [p]
            used = h
        else:
            cur.append(p)
            used += h
    if cur:
        pages.append(cur)
    return pages


def make_cover(total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    draw_chrome(d, 1, total)

    y = CONTENT_TOP + 80
    d.text((PAD, y), "一个月烧200亿AI Token", font=font(66, bold=True), fill=PRIMARY); y += 102
    d.text((PAD, y), "是傻还是真天才？", font=font(66, bold=True), fill=CORAL); y += 120
    d.text((PAD, y), "基于原文全文重排｜大字号版本", font=font(36), fill=SECONDARY); y += 96

    stats = [("200亿", "Token"), ("30", "天"), ("全文", "重排")]
    col_w = CONTENT_W // 3
    for i, (n, t) in enumerate(stats):
        x = PAD + i * col_w
        d.text((x, y), n, font=font(54, bold=True), fill=PRIMARY)
        d.text((x, y+76), t, font=font(28), fill=SECONDARY)

    img.save(os.path.join(OUT_DIR, "card_01.png"))


def make_page(idx, total, paras):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    draw_chrome(d, idx, total)
    y = CONTENT_TOP
    y = section_header(d, "正文", y)
    fb = font(SZ_BODY)
    for p in paras:
        y = draw_text(d, p, PAD, y, fb, PRIMARY, CONTENT_W)
        y += PARA_GAP
    img.save(os.path.join(OUT_DIR, f"card_{idx:02d}.png"))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    paras = load_paragraphs(SRC_MD)
    pages = paginate(paras)
    total = 1 + len(pages)

    make_cover(total)
    for i, paras_on_page in enumerate(pages, start=2):
        make_page(i, total, paras_on_page)

    print(f"✅ Done. cards={total}, output={OUT_DIR}")


if __name__ == "__main__":
    main()
