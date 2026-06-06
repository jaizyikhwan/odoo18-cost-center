# Demo Recording Guide

> A 30-second screen recording that demonstrates the **hard-block** of
> the Cost Center & Budget Control module.

This document provides a script and the commands to capture and assemble
the GIF.

---

## Script (30 seconds, 7 shots)

The goal: show the user creating a budget, attempting to post a bill
that would breach it, and getting blocked. Then show the override path.

| Shot | Duration | What to show | What's happening |
|---|---|---|---|
| 1 | 4s | Cost Center list with the demo data | Static visual, sets context |
| 2 | 4s | Budget Plan form (Approved, 1,000,000 IDR planned) | Sets up the constraint |
| 3 | 4s | Click "+ Create" → Vendor Bill | Start of the breach attempt |
| 4 | 5s | Fill in 1,200,000 IDR (over budget), Click Confirm | The error message appears |
| 5 | 5s | **The blocking error** in red | Module does its job |
| 6 | 4s | Switch user to Budget Override Manager, retry | Override path |
| 7 | 4s | Bill posted, chatter shows "Override applied by..." | Audit trail visible |

**Total: 30 seconds.**

### Detailed voiceover (optional)

> "Odoo 18 Community Edition lets you track budgets — but it doesn't
> enforce them. Watch what happens when a vendor bill would breach
> the budget. [Shot 4-5] The transaction is blocked before posting.
> [Shot 6] Budget Override Manager can authorize, but every override
> is logged in chatter. [Shot 7] That's enforcement + governance in
> one workflow."

---

## Recording Setup (macOS)

### Tools

- **Screen capture**: macOS built-in `Cmd+Shift+5` (record selected
  portion) or `ffmpeg`/`QuickTime` for more control
- **GIF conversion**: `ffmpeg` + `gifsicle`, or `Kap` (free, native)
- **Browser**: Chrome (consistent font + smooth animations)
- **Resolution**: 1280×800 (fits LinkedIn well)

### Prerequisite: Demo Data

Make sure the Odoo instance has the module's demo data loaded:

```bash
# 1. Ensure containers are up
docker compose up -d

# 2. Open http://localhost:8018
# 3. Login as admin (admin / admin)
# 4. Go to Apps → search "Cost Center & Budget Control" → click "Install"
#    (Demo data is enabled by default in the manifest)
```

### Recommended window layout

- Browser in full screen (or 1280×800 window)
- Hide bookmarks bar
- Use a clean user profile (no extensions visible)
- Set Odoo to dark mode if it looks better on LinkedIn

---

## Recording Commands

### Option A: Quick screen capture with `ffmpeg`

```bash
# Record 30 seconds of screen (macOS)
ffmpeg -f avfoundation -i "1:0" -t 30 -r 30 -s 1280x800 \
  -c:v libx264 -preset slow -crf 18 demo_raw.mp4
```

`-i "1:0"` means screen 1 + audio 0. Adjust if you have multiple
displays or want to record voiceover.

### Option B: QuickTime (easiest)

1. Open QuickTime Player
2. File → New Screen Recording
3. Click red button, drag to select the 1280×800 region
4. Click to start, wait 30 seconds, click stop
5. Save as `demo_raw.mov`

### Convert to GIF

```bash
# High-quality GIF (for README hero)
ffmpeg -i demo_raw.mp4 -vf "fps=20,scale=1280:-1:flags=lanczos" \
  -c:v gif -loop 0 demo.gif

# Optimized (smaller file size, for LinkedIn)
ffmpeg -i demo_raw.mp4 -vf "fps=15,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  -loop 0 demo_small.gif
gifsicle -O3 --lossy=30 demo_small.gif -o demo_final.gif
```

Target: **< 5 MB** for LinkedIn upload, **< 2 MB** for README.

### Drop into the repo

```bash
mkdir -p docs/
mv demo_final.gif docs/demo.gif
git add docs/demo.gif
git commit -m "Add 30s demo GIF (hard-block + override flow)"
```

Then reference in README.md:

```markdown
![Demo: hard-block + override flow](docs/demo.gif)
```

---

## Recording Commands (Linux / CI)

If you don't have a display server, you can drive Odoo via XML-RPC and
synthesize the GIF from screenshots:

```python
# scripts/record_demo.py
"""Automated demo recorder. Drives Odoo via XML-RPC and saves a series
of PNG screenshots that can be stitched into a GIF.

Run with: odoo-bin shell -d odoo18_cost_center < scripts/record_demo.py
"""
import time
from PIL import Image

screenshots = []
# (1) Open budget plan list
screenshots.append(env.ref('cost_center_budget_control.action_budget_plan').read()[0])
time.sleep(0.5)
# ... etc

# Stitch with:
#   ffmpeg -framerate 4 -i shots/shot_%02d.png -vf "scale=1280:-1" docs/demo.gif
```

This is more work but reproducible in CI.

---

## Caption / Subtitle (Optional)

If you post the GIF on LinkedIn, the platform auto-plays it on mute.
Adding a single-line caption baked into the GIF dramatically improves
engagement:

```
"Odoo 18 CE: hard-block at posting + role-based override"
```

Use `ffmpeg` to burn in:

```bash
ffmpeg -i demo.gif -vf "drawtext=text='Hard-block at posting + role-based override':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=10:x=(w-text_w)/2:y=h-50" \
  -y demo_captioned.gif
```

---

## Checklist Before Publishing

- [ ] GIF is < 5 MB
- [ ] First frame is recognizable (not a loading spinner)
- [ ] Final frame shows the audit trail, not a "click to continue"
- [ ] No personal data (PII) in the visible records — use generic names
- [ ] Font is readable at LinkedIn's default playback size
- [ ] Demo data is the same as the screenshots in README (consistency)
- [ ] File is committed to `docs/demo.gif`, not `static/img/`

---

## Alternative: Hosted Video (LinkedIn prefers MP4)

LinkedIn's algorithm favours native video over GIF. If you want
maximum reach:

1. Record 30s MP4 (QuickTime or `ffmpeg`)
2. Upload directly to LinkedIn post (don't link YouTube)
3. Add captions via LinkedIn's built-in editor
4. In the GitHub README, link to the LinkedIn post or embed the
   LinkedIn URL

LinkedIn auto-plays MP4 inline, gets 3–5× more reach than a GIF or
image carousel.

---

## Where to Use the Demo

- `docs/demo.gif` — committed, referenced in README
- LinkedIn post
- Personal portfolio site
- Odoo Apps store listing (if you publish there later)
- Conference talk slides (loop on a "demo" slide)
