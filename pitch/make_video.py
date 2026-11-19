"""Builds pitch/demo-backup.mp4 from the captured screens in pitch/demo-frames/.

The frames are real screenshots of the running app (Docker stack, localhost:8080),
captured step by step. The video has captions and no audio.
Run: python pitch/make_video.py
"""
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
W, H = 1280, 720
FPS = 5
BG = (13, 43, 48)
INK = (233, 242, 238)
ACC = (61, 220, 151)
MUTED = (160, 190, 190)

FONT = r"C:\Windows\Fonts\arial.ttf"
BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def card(lines, secs):
    """Text card: list of (text, size, bold, color)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = 120
    for text, size, bold, color in lines:
        f = font(size, bold)
        for ln in wrap(d, text, f, W - 200):
            d.text((100, y), ln, font=f, fill=color)
            y += int(size * 1.3)
        y += 18
    return img, secs


def shot(n, caption, secs=6):
    src = Image.open(HERE / "demo-frames" / f"{n:02d}.jpg").convert("RGB")
    scale = 2.0
    s = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)  # 1154x648
    img = Image.new("RGB", (W, H), BG)
    img.paste(s, ((W - s.width) // 2, 8))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 64, W, H], fill=(7, 23, 32))
    f = font(24, True)
    lines = wrap(d, caption, f, W - 60)
    y = H - 60 + (52 - 28 * len(lines)) // 2
    for ln in lines:
        d.text((30, y), ln, font=f, fill=INK)
        y += 28
    return img, secs


def main():
    seq = [
        card([("Cash Shield (Sabyr)", 64, True, INK),
              ("Backup walkthrough of the live demo", 36, False, ACC),
              ("Real screens of the running app, captured step by step. No audio.", 30, False, MUTED),
              ("All data is synthetic. The bank's authorization host is mocked.", 30, False, MUTED)], 5),
        shot(1, "1. Gülnar apa (a made-up customer) is at the ATM. A loan 3 hours ago. Balance 3 000 000 ₸."),
        shot(2, "2. First 500 000 ₸ withdrawal: score 45, so the ATM asks one question."),
        shot(3, "3. The scammer taught her to answer No. The cash comes out. This loss is shown on purpose."),
        shot(4, "4. Second withdrawal, other ATM, camera off: score 95. The ATM stops and dispenses nothing."),
        shot(5, "5. Cash desk, Bolat, 2 500 000 ₸: score 65. The teller sees the reasons: do not pay out."),
        shot(6, "6. App, Aigerim: deposit closed, 2 000 000 ₸ to a new person: score 75, 30-minute pause."),
        shot(7, "7. Officer console: three held cases, each with its reasons. 1 trusted person notified (simulated).", 7),
        shot(8, "8. Releasing a false alarm needs a written comment from the officer."),
        shot(9, "9. Released. The counter shows 1 false alarm; the other two stay on hold."),
        card([("Result on 180 synthetic scenarios, measured once", 40, True, INK),
              ("78.3% of fraud stopped (target 85%, missed)", 36, False, ACC),
              ("4.2% of normal customers bothered, 0% paused", 36, False, ACC),
              ("Age fairness gap 8.3 pp: FAIL (limit 8 pp)", 36, False, (255, 142, 134)),
              ("Scripted red team: 4 of 10 attempts got through", 36, False, (242, 184, 75)),
              ("Reproduce: python tasks.py eval", 30, False, MUTED)], 9),
    ]
    out = HERE / "demo-backup.mp4"
    with imageio.get_writer(out, fps=FPS, codec="libx264", quality=7, pixelformat="yuv420p",
                            macro_block_size=16) as w:
        for img, secs in seq:
            arr = np.asarray(img)
            for _ in range(int(secs * FPS)):
                w.append_data(arr)
    total = sum(s for _, s in seq)
    print(f"wrote {out} ({total} s, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
