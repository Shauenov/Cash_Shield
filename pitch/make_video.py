"""Builds pitch/demo-backup.mp4 from the captured screens in pitch/demo-frames/.

The frames are real screenshots of the running app (production build, Russian interface),
captured step by step on 2026-11-25. The video has Russian captions and no audio.
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
    scale = min((W - 40) / src.width, (H - 80) / src.height)   # fit above the caption band
    s = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
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
              ("Запасная запись живого демо", 36, False, ACC),
              ("Настоящие экраны работающего приложения, снятые по шагам. Без звука.", 30, False, MUTED),
              ("Все данные синтетические. Хост авторизации банка имитирован.", 30, False, MUTED)], 5),
        shot(1, "1. Гүлнар апа (вымышленная клиентка) у банкомата. Кредит взят 3 часа назад, баланс 3 000 000 ₸."),
        shot(2, "2. Первое снятие 500 000 ₸: 45 баллов, банкомат задаёт один вопрос."),
        shot(3, "3. Мошенник научил её отвечать «нет». Наличные выданы: эту потерю показываем намеренно."),
        shot(4, "4. Второе снятие, другой банкомат, камера выключена: 95 баллов. Банкомат ничего не выдаёт."),
        shot(5, "5. Касса, Болат, 2 500 000 ₸: 65 баллов. Кассир видит причины и что сказать: не выдавать."),
        shot(6, "6. Приложение, Айгерим: вклад закрыт, 2 000 000 ₸ новому получателю: 75 баллов, пауза 30 минут."),
        shot(7, "7. Консоль офицера: три операции ждут решения, у каждой причины. Доверенное лицо уведомлено (имитация).", 7),
        shot(8, "8. Чтобы снять ложную тревогу, офицер обязан написать комментарий."),
        shot(9, "9. Пауза снята: счётчик показывает 1 ложную тревогу, две операции остаются на удержании."),
        card([("Итог на 180 синтетических сценариях, замер один раз", 40, True, INK),
              ("Остановлено 78,3% мошенничества (цель 85% не достигнута)", 34, False, ACC),
              ("Потревожено 4,2% честных клиентов, на паузе 0%", 34, False, ACC),
              ("Разница ложных тревог по возрасту 8,3 п.п.: FAIL (предел 8)", 34, False, (255, 142, 134)),
              ("Правила v2 на новой выборке: 67,4% -> 76,7%, демо на v1", 34, False, (242, 184, 75)),
              ("Повторить: python tasks.py eval", 30, False, MUTED)], 9),
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
