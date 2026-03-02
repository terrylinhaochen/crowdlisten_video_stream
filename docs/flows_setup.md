# Unified Flows Setup (OpenClaw-first)

This project now supports two major pipelines:

1) Long-form content -> multi-channel short-form drafts
2) Video processing -> clip analysis + reels rendering

And one card-post pipeline:
- Chinese long-form -> Xiaohongshu-style image cards

## Control Surface
Use one command entrypoint:

```bash
scripts/flowctl.sh <command>
```

## Commands

### 1) Validate setup
```bash
scripts/flowctl.sh check
```
Checks required scripts, Studio backend, and CLI smoke tests.

### 2) Long-form -> multi-channel drafts
```bash
scripts/flowctl.sh content --input notes/token_experiment_zh.md --platforms blog,linkedin,thread --version v1
```
Backed by `scripts/content_gen.py`.

### 3) Chinese card generation (OpenClaw processing)
```bash
scripts/flowctl.sh cards fulltext
```
Output folder:
- `content_gen/token_experiment_zh_cards/v3_fulltext`

For paragraph-gap readable variant:
- `content_gen/token_experiment_zh_cards/v4_fulltext_paragraph_gap`

### 4) Video clip analysis
```bash
scripts/flowctl.sh analyze-video marketing_clips/siliconvalley1.mp4 --clips 12
```
Backed by `scripts/analyze_video.py`.

### 5) Reels rendering batch
```bash
scripts/flowctl.sh render-reels
```
Backed by `scripts/render_reels.py` clip config.

### 6) Start Studio GUI
```bash
scripts/flowctl.sh studio-start
```

## Architecture Decision
- Studio GUI remains browse/review/publish hub.
- Heavy generation logic stays script/OpenClaw-driven for fast iteration.
- No additional mandatory backend APIs required for card generation.

## Related Docs
- `docs/content_gen.md`
- `docs/whisper_workflow.md`
- `docs/token_xiaohongshu_cards_workflow.md`
- `docs/studio_openclaw_cards_integration.md`
