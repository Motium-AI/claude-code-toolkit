---
name: episode
description: >
  Generate educational video episodes with Minecraft-style graphics. Orchestrates
  fal.ai (Kling video, Flux images), ElevenLabs TTS, and FFmpeg assembly into
  complete episodes. Use when asked to "generate an episode", "create educational
  video", "produce an episode", or "/episode".
---

# Educational Video Episode Generator (/episode)

Autonomous skill that generates complete educational video episodes with Minecraft-style
graphics. Claude acts as Creative Director, writing the script and orchestrating
AI generation APIs to produce the final video.

## Architecture

```
/episode "How photosynthesis works"
    │
    ├── Phase 0: Activation (state file, dependency check)
    ├── Phase 1: Script Generation (Claude writes episode script as JSON manifest)
    ├── Phase 2: Media Generation (pipeline.py calls APIs)
    │   ├── Images: Flux via fal.ai
    │   ├── Video clips: Kling I2V via fal.ai
    │   ├── Audio: ElevenLabs TTS
    │   └── Assembly: FFmpeg
    ├── Phase 3: Review (human watches output)
    └── Phase 4: Complete (checkpoint validation)
```

## Triggers

- `/episode <topic>`
- "generate an episode about..."
- "create educational video on..."
- "produce an episode explaining..."

## Phase 0: Activation

### State File (Automatic)

Create `.claude/autonomous-state.json` with `"mode": "episode"` at activation.

### Dependency Check

Before proceeding, verify dependencies are installed:

```bash
python3 -c "import fal_client; import elevenlabs" 2>/dev/null || {
    echo "Installing dependencies..."
    pip3 install fal-client elevenlabs
}
```

### API Keys Check

Required environment variables:
- `FAL_KEY` - fal.ai API key
- `ELEVENLABS_API_KEY` - ElevenLabs API key

```bash
[ -z "$FAL_KEY" ] && echo "ERROR: FAL_KEY not set" && exit 1
[ -z "$ELEVENLABS_API_KEY" ] && echo "ERROR: ELEVENLABS_API_KEY not set" && exit 1
```

If missing, ask the user ONCE at start, then proceed autonomously.

## Phase 1: Script Generation (Claude as Creative Director)

You ARE the creative director. Write the episode script as a JSON manifest.

### Episode Structure: The 7-Act Framework

Every episode follows this learning-science-backed narrative structure:

| Act | Duration | Purpose | Minecraft Metaphor |
|-----|----------|---------|-------------------|
| **SPARK** | 1 scene | Hook with wonder/mystery | Discovering a glowing ore |
| **QUEST** | 2 scenes | Frame learning as journey | Setting out from spawn |
| **MAP** | 2 scenes | Overview before deep dive | Crafting a map |
| **MINE** | 4-5 scenes | Core concept exploration | Mining at different depths |
| **CRAFT** | 3 scenes | Synthesis, the "aha" moment | Crafting table assembly |
| **BUILD** | 3 scenes | Application, abstract→concrete | Building a structure |
| **PORTAL** | 2 scenes | Climax + "what's next" hook | Activating a portal |

### Scene Count by Duration

| Episode Duration | Total Scenes | Clips per Scene | Total Clips |
|-----------------|--------------|-----------------|-------------|
| 3 minutes | 12-15 scenes | 1-2 clips | 15-20 clips |
| 10 minutes | 18-22 scenes | 2-3 clips | 40-50 clips |

### Minecraft Visual Style Guide

**ALWAYS include this prefix in visual prompts:**

> "Minecraft-style 3D voxel world. Blocky cubic geometry, pixel-art textures,
> warm ambient lighting. Characters are blocky humanoid figures with square heads.
> Bright saturated colors, soft shadows. Low-poly aesthetic."

**Visual Metaphor Dictionary:**

| Abstract Concept | Minecraft Visual |
|-----------------|------------------|
| Variable | Chest with name tag |
| Function | Redstone circuit |
| Data flow | Minecart on rails |
| Memory | Storage room with chests |
| Error/bug | Creeper hiding in build |
| Process | Furnace smelting |
| Input/Output | Hopper feeding items |
| Hierarchy | Stacked blocks, scaffolding |
| Connection | Redstone wire linking blocks |
| Transformation | Crafting animation |

### Manifest Schema

Create the manifest at `episodes/EP{NNN}/manifest.json`:

```json
{
  "episode_id": "EP001",
  "title": "How Photosynthesis Works",
  "topic": "photosynthesis",
  "target_duration_seconds": 180,
  "style": "minecraft",
  "created_at": "2026-01-30T21:00:00Z",
  "cost_budget_usd": 25.00,
  "cost_spent_usd": 0.00,

  "scenes": [
    {
      "scene_id": "scene-001",
      "sequence": 1,
      "act": "SPARK",
      "duration_seconds": 10,
      "narration": "What if I told you that every leaf is a tiny factory?",
      "visual_prompt": "Minecraft-style forest clearing at sunrise. Sunbeams pierce through blocky oak leaves. Golden light particles float in the air. A blocky character looks up in wonder at the glowing canopy.",
      "camera": "slow_pan_up",
      "music_mood": "wonder",

      "image": {
        "status": "pending",
        "fal_request_id": null,
        "asset_path": null,
        "cost_usd": 0
      },
      "clip": {
        "status": "pending",
        "fal_request_id": null,
        "asset_path": null,
        "cost_usd": 0
      },
      "audio": {
        "status": "pending",
        "asset_path": null,
        "cost_usd": 0
      }
    }
  ],

  "assembly": {
    "status": "pending",
    "asset_path": null
  }
}
```

### Writing the Script

1. **Create episode directory:**
   ```bash
   mkdir -p episodes/EP001/assets/{images,clips,audio}
   ```

2. **Write manifest.json** with all scenes following the 7-act structure

3. **Each scene needs:**
   - `narration`: What the narrator says (10-20 words per 10s)
   - `visual_prompt`: Detailed Minecraft-style visual description (include style prefix)
   - `camera`: Camera movement (static, slow_pan, zoom_in, tracking)
   - `duration_seconds`: 8-15 seconds per scene

## Phase 2: Media Generation

Run the pipeline script to generate all media:

```bash
python3 ~/.claude/skills/episode/scripts/pipeline.py episodes/EP001/manifest.json
```

The script handles:
1. **Images** → Flux via fal.ai (~3-10s per image)
2. **Video clips** → Kling I2V via fal.ai (~60-180s per clip)
3. **Audio** → ElevenLabs TTS (~2-5s per scene)
4. **Assembly** → FFmpeg concat with crossfades

### Monitoring Progress

The manifest is updated after each operation. Check progress:

```bash
cat episodes/EP001/manifest.json | jq '.scenes[] | {scene_id, image: .image.status, clip: .clip.status, audio: .audio.status}'
```

### Resume from Checkpoint

If the pipeline crashes or times out, simply re-run:

```bash
python3 ~/.claude/skills/episode/scripts/pipeline.py episodes/EP001/manifest.json
```

The script reads the manifest and skips completed work.

### Cost Tracking

The manifest tracks costs per operation. Check total:

```bash
cat episodes/EP001/manifest.json | jq '.cost_spent_usd'
```

Expected costs:
- 3-minute episode: $15-22
- 10-minute episode: $48-68

## Phase 3: Review

After pipeline completes, the final video is at:

```
episodes/EP001/episode.mp4
```

**Human review is required.** Watch the video and verify:
- [ ] Narration is clear and educational
- [ ] Visuals match the Minecraft style
- [ ] Pacing feels natural
- [ ] No jarring cuts or artifacts
- [ ] Audio levels are balanced

## Phase 4: Complete

### Completion Checkpoint Schema

```json
{
  "self_report": {
    "code_changes_made": true,
    "is_job_complete": true
  },
  "reflection": {
    "what_was_done": "Generated 3-min episode 'How Photosynthesis Works' with 15 scenes",
    "what_remains": "none"
  },
  "evidence": {
    "episode_path": "episodes/EP001/episode.mp4",
    "manifest_path": "episodes/EP001/manifest.json",
    "cost_usd": 18.50,
    "duration_seconds": 182,
    "scene_count": 15
  }
}
```

## Troubleshooting

### fal.ai Queue Timeout

If Kling takes too long (>5 min per clip), the script may timeout. Just re-run:

```bash
python3 ~/.claude/skills/episode/scripts/pipeline.py episodes/EP001/manifest.json --phase clips
```

### Rate Limits

The script caps concurrent video submissions to 3. If you hit rate limits, wait 60 seconds and re-run.

### Style Drift

If later clips look less "Minecraft-like", the I2V model may be drifting. Regenerate the keyframe image with a stronger style prompt and re-run the clip generation.

### FFmpeg Errors

Ensure FFmpeg is installed:

```bash
which ffmpeg || brew install ffmpeg
```

## API Reference

### fal.ai Endpoints

| Model | Endpoint | Use |
|-------|----------|-----|
| Flux Dev | `fal-ai/flux/dev` | Keyframe images |
| Kling 2.1 | `fal-ai/kling-video/v2.1/pro/image-to-video` | Video clips |

### ElevenLabs

| Model | Voice ID | Use |
|-------|----------|-----|
| Eleven Multilingual v2 | `JBFqnCBsd6RMkjVDRZzb` (George) | Narration |

## Example: 3-Minute Episode on Photosynthesis

```bash
# 1. Invoke the skill
/episode "How photosynthesis works"

# 2. Claude writes the script (manifest.json with 15 scenes)

# 3. Run the pipeline
python3 ~/.claude/skills/episode/scripts/pipeline.py episodes/EP001/manifest.json

# 4. Watch the output
open episodes/EP001/episode.mp4

# 5. Update checkpoint and complete
```

## Philosophy

This skill embodies the Namshub principle: **Claude is the intelligence, APIs are the tools.**

Claude doesn't just call APIs. Claude is the creative director who:
- Writes compelling educational narratives
- Designs visual metaphors that make abstract concepts tangible
- Paces the episode for engagement and retention
- Makes intentional creative decisions at every step

The APIs generate pixels and audio. Claude provides the vision.
