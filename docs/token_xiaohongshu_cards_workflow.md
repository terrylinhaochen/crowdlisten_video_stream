# Token Experiment Chinese Card Workflow (Xiaohongshu-style)

This documents the workflow used to turn long Chinese text into branded image cards with large typography and readable spacing.

## Goal
Generate multi-card PNG posts (1080x1350) from Chinese long-form text, with:
- Large font
- CJK-aware wrapping
- Balanced vertical layout
- Optional paragraph spacing
- Full-text or condensed versions

## Reference Style
Based on:
- `content_gen/agentic_engineering_zh/generate.py`

Core visual style:
- Background: `#F7F5F2`
- Accent coral: `#D97D55`
- Font: `/System/Library/Fonts/PingFang.ttc`
- Header + footer chrome on every card

## Source Text
- Input markdown:
  - `notes/token_experiment_zh.md`

## Implemented Scripts
Location:
- `content_gen/token_experiment_zh_cards/`

Scripts:
1. `generate.py`
   - First compact version
   - 8 cards, reduced copy

2. `generate_v2.py`
   - Closer to original article
   - 10 cards
   - Title used:
     - "一个月烧200亿AI Token，是傻还是真天才？"

3. `generate_v3_fulltext.py`
   - Full-text pagination
   - Large font mode

4. `v4_fulltext_paragraph_gap` (generated via one-off terminal script)
   - Full-text pagination + explicit paragraph gap
   - Best for readability when publishing text-heavy carousel cards

## Output Directories
- `content_gen/token_experiment_zh_cards/v1`
- `content_gen/token_experiment_zh_cards/v2`
- `content_gen/token_experiment_zh_cards/v3_fulltext`
- `content_gen/token_experiment_zh_cards/v4_fulltext_paragraph_gap`

## Recommended Default (for future runs)
Use **full-text + paragraph gap** settings:
- Body font size: `35`
- Line spacing multiplier: `1.42`
- Paragraph gap: `30`
- Canvas: `1080 x 1350`
- Horizontal padding: `64`

## Regeneration Commands
From terminal:

```bash
python3 content_gen/token_experiment_zh_cards/generate_v2.py
python3 content_gen/token_experiment_zh_cards/generate_v3_fulltext.py
```

For paragraph-gap version, keep a dedicated script file (recommended next cleanup step) instead of ad-hoc inline Python.

## Practical Notes
- If card pages look half-empty:
  - Increase paragraph density (more text per page), or
  - Reduce paragraph gap, or
  - Increase total card count less aggressively.
- If text feels cramped:
  - Keep font size, increase card count.
- For Chinese readability, avoid over-condensing punctuation-heavy paragraphs.

## Future Improvement
Create a single configurable generator:
- `generate_cards.py --mode fulltext --font-size 35 --paragraph-gap 30 --title "..."`

This removes one-off script edits and makes iteration faster.
