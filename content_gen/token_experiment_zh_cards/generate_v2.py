#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "v2")
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"

W, H = 1080, 1350
PAD = 68
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
TOTAL = 10

SZ_HEADER = 40
SZ_BODY = 31


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


def text_block(draw, text, x, y, fnt, color, max_w, ls=1.48):
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
    num = f"{card_n:02d}  /  {TOTAL:02d}"
    nb = draw.textbbox((0,0), num, font=font(22, bold=True))
    draw.text((W - PAD - (nb[2]-nb[0]), fy+2), num, font=font(22, bold=True), fill=SECONDARY)
    draw.line([(PAD, HEADER_TOP+HEADER_H), (W-PAD, HEADER_TOP+HEADER_H)], fill=DIVIDER, width=1)
    draw.line([(PAD, CONTENT_BOTTOM+16), (W-PAD, CONTENT_BOTTOM+16)], fill=DIVIDER, width=1)
    draw.text((PAD, CONTENT_BOTTOM+28), "Terry Chen  ·  chenterry.com", font=font(20), fill=SECONDARY)


def new_card():
    return Image.new("RGB", (W, H), BG), None


def section_header(draw, title, y):
    fnt = font(SZ_HEADER, bold=True)
    bar_h = int(SZ_HEADER * 1.2)
    draw.rectangle([PAD, y, PAD+6, y+bar_h], fill=CORAL)
    draw.text((PAD+18, y+2), title, font=fnt, fill=PRIMARY)
    return y + bar_h + 20


def save_content_card(i, title, paragraphs):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw_chrome(draw, i)
    y = CONTENT_TOP
    y = section_header(draw, title, y)
    fb = font(SZ_BODY)
    for p in paragraphs:
        y = text_block(draw, p, PAD, y, fb, PRIMARY, CONTENT_W)
        y += 14
    img.save(os.path.join(OUT_DIR, f"card_{i:02d}.png"))
    print(f"card_{i:02d}.png ✓")


def cover():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw_chrome(draw, 1)

    y = CONTENT_TOP + 100
    draw.text((PAD, y), "一个月烧200亿AI Token", font=font(66, bold=True), fill=PRIMARY)
    y += 100
    draw.text((PAD, y), "是傻还是真天才？", font=font(66, bold=True), fill=CORAL)
    y += 120
    draw.text((PAD, y), "拿到 OpenAI credit 后，我决定做一次极端实验。", font=font(36), fill=SECONDARY)
    y += 80

    stats = [("200亿", "Token"), ("30", "天"), ("2", "核心问题")]
    col_w = CONTENT_W // 3
    for idx, (n, t) in enumerate(stats):
        x = PAD + idx * col_w
        draw.text((x, y), n, font=font(54, bold=True), fill=PRIMARY)
        draw.text((x, y+76), t, font=font(28), fill=SECONDARY)

    img.save(os.path.join(OUT_DIR, "card_01.png"))
    print("card_01.png ✓")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cover()

    save_content_card(2, "我要回答的两个问题", [
        "最近拿到了一笔 OpenAI 的 AI credit，我决定做一个有点极端的实验：在一个月内，烧掉 200 亿 token。",
        "我想回答两个问题：",
        "（1）AI 除了工程之外，在其他运营任务上到底应该怎么用？",
        "（2）用 AI 做出的“最有价值的产品”，长什么样？",
    ])

    save_content_card(3, "起点：生产主体会变化", [
        "这件事的起点，是我最近一直反复在想的一个问题。过去一段时间，我一直在写一个关于 Agent 的产品 thesis。",
        "其中一个核心判断是：未来不管是信息检索还是任务执行，生产的主体很可能会从“人”逐渐转向“Agent”。",
        "如果这件事真的发生，变化可能不只是效率提升，而是会连带改变很多我们已经习以为常的产品形态。",
    ])

    save_content_card(4, "广告会先被重写", [
        "比如广告。",
        "如果未来真正“消费信息”的不再是人，而是 Agent，那广告到底是给谁看的？",
        "今天围绕点击率和转化路径设计的一整套逻辑，可能都需要被重新定义。",
    ])

    save_content_card(5, "界面也会被重写", [
        "再比如界面。",
        "随着多模态 Agent 和手机侧 Agent 的发展，其实已经能看到一个趋势：很多任务可以直接让 Agent 完成。",
        "在这种情况下，复杂 GUI 反而会变成一种负担——人未必看得懂，操作成本也高。",
        "如果任务可以被清晰表达，那直接让 Agent 执行，体验反而更好。",
    ])

    save_content_card(6, "工具层已经在变化", [
        "类似的变化，其实已经在工具层开始发生。",
        "现在很多开发工具，比如数据库、后端服务、邮件系统，如果做得足够标准化，Agent 在执行任务时是可以直接调用的。",
        "像 Supabase、Resend 这一类服务，正在逐渐变成“Agent 默认可用的基础设施”。",
    ])

    save_content_card(7, "很多产品要重做一遍", [
        "但这可能只是第一层变化。再往下一层，会不会有更多原本“为人设计”的产品，需要被重新做一遍？",
        "比如 Yelp 这种，本质是给人看的信息浏览和决策工具。如果未来是 Agent 帮你选餐厅，产品形态会不会完全不一样？",
        "再比如大量 SaaS 工具，今天的交互逻辑和信息结构，很多都围绕“人如何理解和操作”设计；如果使用者变成 Agent，这一套是不是要被重构？",
    ])

    save_content_card(8, "机会：Agent 版产品", [
        "这背后会出现一个很现实的机会：有些公司很难快速完成这种转变，而“为 Agent 设计”的产品形态，本身可能就是一条新的路径。",
        "甚至有些服务，可能需要同时存在两种版本——一套给人用，一套给 Agent 用。",
        "从组织层面看，我最近越来越在意一个更底层的问题：如果生产主体真的从人转向 Agent，企业之间的竞争力会变成什么？",
    ])

    save_content_card(9, "Token ROI", [
        "我现在的直觉是：未来公司之间比的，可能不再是传统意义上的“人效”，而是一个更直接的指标——Token ROI。",
        "同样消耗一千个 token，有的团队只是生成一段内容；有的团队却能把它变成一个功能、一个增长点，甚至直接转化成收入。",
        "Token 成本在不断下降，但真正拉开差距的，是你能不能用这些计算创造出实际价值。",
    ])

    save_content_card(10, "这个月我要验证什么", [
        "换句话说，你消耗多少 token 并不重要，重要的是这些 token 最终换来了什么。",
        "所以这次“200 亿 token”实验，对我来说不只是一个烧钱挑战，更像是在验证一件事：",
        "当你不再刻意节省 token，而是反过来放大计算、让 Agent 去处理更多不确定性时，产品会不会走向一种完全不同的形态。",
        "接下来一个月，我会持续记录：哪些 token 有效、哪些 token 浪费，以及能不能真的跑出一个有价值的产品。",
    ])

    print(f"\n✅ Done. Output -> {OUT_DIR}")


if __name__ == "__main__":
    main()
