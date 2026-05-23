from pathlib import Path

from PIL import Image, ImageDraw


def create_normal_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([2, 2, size - 2, size - 2], fill=(60, 80, 120, 230))

    cx = size // 2
    mic_w = max(6, size // 6)
    mic_h = max(10, size // 3)
    body_top = size // 6
    body_bottom = body_top + mic_h
    r = mic_w // 2

    draw.rounded_rectangle(
        [cx - mic_w, body_top, cx + mic_w, body_bottom],
        radius=r,
        fill=(200, 220, 255),
    )

    arc_margin = mic_w * 2
    arc_top = body_bottom - mic_w
    arc_bottom = body_bottom + mic_w
    draw.arc(
        [cx - arc_margin, arc_top, cx + arc_margin, arc_bottom],
        start=0,
        end=180,
        fill=(200, 220, 255),
        width=max(2, size // 20),
    )

    stem_x = cx
    stem_top = body_bottom + mic_w // 2
    stem_bottom = body_bottom + mic_w + max(2, size // 16)
    line_w = max(2, size // 20)
    draw.line([stem_x, stem_top, stem_x, stem_bottom], fill=(200, 220, 255), width=line_w)

    base_half = mic_w
    draw.line(
        [stem_x - base_half, stem_bottom, stem_x + base_half, stem_bottom],
        fill=(200, 220, 255),
        width=line_w,
    )

    return img


def create_recording_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([2, 2, size - 2, size - 2], fill=(200, 30, 30, 230))

    r = size // 5
    cx, cy = size // 2, size // 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255))

    return img


def create_processing_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([2, 2, size - 2, size - 2], fill=(180, 100, 20, 230))

    dot_r = max(3, size // 14)
    cy = size // 2
    spacing = size // 4
    for i in range(3):
        x = spacing + i * spacing
        draw.ellipse([x - dot_r, cy - dot_r, x + dot_r, cy + dot_r], fill=(255, 255, 255))

    return img


def save_ico_file(path: Path) -> Path:
    """Erstellt eine .ico-Datei mit mehreren Auflösungen (16–256 px).

    Wird für Verknüpfungen und den Windows-Installer benötigt.
    Gibt den Pfad zur erstellten .ico-Datei zurück.
    """
    path = Path(path)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [create_normal_icon(s).convert("RGBA") for s in sizes]
    # PIL speichert alle Größen als Multi-Resolution-ICO
    images[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    return path
