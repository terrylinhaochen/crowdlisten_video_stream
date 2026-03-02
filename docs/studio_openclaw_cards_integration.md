# CrowdListen Studio × OpenClaw Card Generation (OpenClaw-first)

## Decision
Use **OpenClaw as the processor** for long-form Chinese card generation.

Studio remains GUI for:
- browsing outputs
- reviewing assets
- publishing workflow

But generation itself runs via OpenClaw-triggered scripts, not a new Studio API flow.

---

## Why this approach
- Keeps heavy text-processing logic in scripts/OpenClaw (faster iteration)
- Avoids adding/maintaining another backend API surface in Studio
- Better for ad-hoc prompt/content updates from chat

---

## Canonical generator
Directory:
- `content_gen/token_experiment_zh_cards/`

Primary script right now:
- `generate_v3_fulltext.py` (full text, large font)

Paragraph-gap variant output:
- `v4_fulltext_paragraph_gap/` (best readability for text-heavy posts)

---

## Run model (recommended)
From OpenClaw chat, run one of:

```bash
python3 /Users/terry/Desktop/crowdlisten_files/crowdlisten_marketing/content_gen/token_experiment_zh_cards/generate_v3_fulltext.py
```

or paragraph-gap build via dedicated script when available.

---

## Studio status
- Studio already has `/api/content-gen` for copy drafts.
- Studio is **not** yet the source of truth for this card-generation pipeline.
- Current source of truth = card generator scripts + output folders.

---

## Next optional step (if needed)
If GUI triggering becomes necessary later, add a thin wrapper button in Studio that simply executes existing scripts and returns output path (no business logic in API layer).
