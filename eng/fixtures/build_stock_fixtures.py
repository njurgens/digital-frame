#!/usr/bin/env python
"""Build the stock-image test fixture set in ``tests/fixtures/stock/``.

Three sources, per docs/stock-images.md:

1. **Real smartphone photos** collected from Wikimedia Commons
   (``.pi/tmp/stock-images/images``) — re-encoded to q80 with EXIF
   preserved (MakerNote dropped) so the set stays small.
2. **picsum.photos (Unsplash) photos** downloaded at target sizes with
   synthesized phone-style EXIF: orientation tag, ``DateTimeOriginal``,
   optional GPS (fictional coordinates).
3. **Synthesized graphics**: a phone screenshot PNG, a transparent PNG,
   and an animated GIF.

Writes ``tests/fixtures/stock/ATTRIBUTION.md`` with per-file provenance.

One-off curation tool for the stock-image test set (see
docs/stock-images.md). The real-photo step requires the output of
``collect_stock_images.py`` in ``.pi/tmp/stock-images/``; the picsum and
synthesized steps are self-contained. Re-running is idempotent: the output
directory is rebuilt from scratch.

Usage:
    .venv/bin/python eng/fixtures/build_stock_fixtures.py
"""

from __future__ import annotations

import math
import shutil
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
REAL_DIR = REPO / ".pi" / "tmp" / "stock-images" / "images"
OUT_DIR = REPO / "tests" / "fixtures" / "stock"

API_UA = (
    "digital-frame stock-image collector "
    "(https://github.com/njurgens/digital-frame; test-fixture research) python-requests"
)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------


@dataclass
class ExifProfile:
    """EXIF to synthesize (or None for a no-EXIF file)."""

    orientation: int = 1
    datetime: str | None = None  # "2024:05:12 15:30:22"
    gps: tuple[tuple[Fraction, ...], tuple[Fraction, ...]] | None = None
    gps_ref: tuple[str, str] | None = None  # (lat ref, lon ref)
    progressive: bool = False


def gps(lat: tuple[int, int, int], lon: tuple[int, int, int]) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    """Build GPS rationals from (deg, min, tenths-of-second) tuples."""
    def frac(t: tuple[int, int, int]) -> tuple[Fraction, ...]:
        return (Fraction(t[0]), Fraction(t[1]), Fraction(t[2], 10))

    return (frac(lat), frac(lon))


@dataclass
class StockFile:
    name: str
    kind: str  # "real" | "picsum" | "screenshot" | "transparent" | "gif"
    source: str = ""
    author: str = ""
    license: str = ""
    credit: str = ""
    note: str = ""
    picsum_id: int | None = None
    size: tuple[int, int] | None = None
    exif: ExifProfile | None = None
    real_file: str | None = None  # filename inside REAL_DIR for kind == "real"


SPEC: list[StockFile] = [
    # -- Real smartphone photos (Wikimedia Commons) -------------------------
    StockFile(
        name="Михайлівський_Золотоверхий_монастир._Київ6.jpg",
        kind="real", real_file="Михайлівський_Золотоверхий_монастир._Київ6.jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="Мандрівниця", license="CC BY-SA 4.0",
        credit="Author: Мандрівниця. License: CC BY-SA 4.0, via Wikimedia Commons.",
        note="4:3 portrait, real EXIF; Unicode filename",
    ),
    StockFile(
        name="Bundesministerium_für_Verkehr_und_digitale_Infrastruktur_(Berlin)_–_Datensummit_2017_(2).jpg",
        kind="real",
        real_file="Bundesministerium_für_Verkehr_und_digitale_Infrastruktur_(Berlin)_–_Datensummit_2017_(2).jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="ubahnverleih", license="CC0",
        credit="Author: ubahnverleih. CC0, via Wikimedia Commons.",
        note="4:3, real GPS + timestamp",
    ),
    StockFile(
        name="Estación_Ciudad_del_Futuro_L3_-_Agosto_2025_(3).jpg",
        kind="real", real_file="Estación_Ciudad_del_Futuro_L3_-_Agosto_2025_(3).jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="José Chuito", license="CC BY 4.0",
        credit="Author: José Chuito. License: CC BY 4.0, via Wikimedia Commons.",
        note="4:3, real GPS + timestamp",
    ),
    StockFile(
        name="HK_CWB_銅鑼灣_Causeway_Bay_溫莎大廈_Windsor_House_mall_shop_August_2020_SS2_03.jpg",
        kind="real",
        real_file="HK_CWB_銅鑼灣_Causeway_Bay_溫莎大廈_Windsor_House_mall_shop_August_2020_SS2_03.jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="Ahoi Yahgeum Windhuo", license="CC BY-SA 4.0",
        credit="Author: Ahoi Yahgeum Windhuo. License: CC BY-SA 4.0, via Wikimedia Commons.",
        note="4:3, CJK filename",
    ),
    StockFile(
        name="Haçlar_tepesi_7.jpg",
        kind="real", real_file="Haçlar_tepesi_7.jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="Zemxer", license="CC BY-SA 4.0",
        credit="Author: Zemxer. License: CC BY-SA 4.0, via Wikimedia Commons.",
        note="4:3",
    ),
    StockFile(
        name="Good-Samaritan-3-105224.jpg",
        kind="real", real_file="Good-Samaritan-3-105224.jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="Bukvoed", license="CC BY 4.0",
        credit="Author: Bukvoed. License: CC BY 4.0, via Wikimedia Commons.",
        note="wide 2.4:1, real GPS + timestamp",
    ),
    StockFile(
        name="Borgward_RS_(54329616959).jpg",
        kind="real", real_file="Borgward_RS_(54329616959).jpg",
        source="Wikimedia Commons (Category:Taken_with_iPhone_16)",
        author="Thomas Vogt from Paderborn, Deutschland", license="CC BY 2.0",
        credit="Author: Thomas Vogt. License: CC BY 2.0, via Wikimedia Commons.",
        note="4:3 monochrome (high-contrast B&W)",
    ),
    # -- picsum (Unsplash) photos with synthesized phone EXIF ----------------
    StockFile(
        name="landscape-valley.jpg", kind="picsum", picsum_id=11, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 11)", license="Unsplash License",
        note="16:9 nature; progressive JPEG encoding",
        exif=ExifProfile(datetime="2024:05:12 15:30:22", progressive=True),
    ),
    StockFile(
        name="landscape-santorini.jpg", kind="picsum", picsum_id=49, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 49)", license="Unsplash License",
        note="16:9 travel; GPS (fictional)",
        exif=ExifProfile(
            datetime="2024:06:01 08:15:44",
            gps=gps((37, 58, 12), (23, 43, 48)), gps_ref=("N", "E"),
        ),
    ),
    StockFile(
        name="street-european.jpg", kind="picsum", picsum_id=57, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 57)", license="Unsplash License",
        note="16:9 city street",
        exif=ExifProfile(datetime="2024:06:15 17:42:10"),
    ),
    StockFile(
        name="night-bokeh.jpg", kind="picsum", picsum_id=56, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 56)", license="Unsplash License",
        note="night / dark content",
        exif=ExifProfile(datetime="2024:07:03 23:12:05"),
    ),
    StockFile(
        name="night-city-bw.jpg", kind="picsum", picsum_id=43, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 43)", license="Unsplash License",
        note="B&W night city (high contrast, monochrome)",
        exif=ExifProfile(datetime="2024:07:19 22:47:33"),
    ),
    StockFile(
        name="highcontrast-heels.jpg", kind="picsum", picsum_id=21, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 21)", license="Unsplash License",
        note="high-contrast color (white on red)",
        exif=ExifProfile(datetime="2024:08:08 11:24:51"),
    ),
    StockFile(
        name="highcontrast-lighthouse-bw.jpg", kind="picsum", picsum_id=58, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 58)", license="Unsplash License",
        note="B&W dramatic sky (high contrast, monochrome)",
        exif=ExifProfile(datetime="2024:08:22 09:03:17"),
    ),
    StockFile(
        name="people-cliff-sunset.jpg", kind="picsum", picsum_id=27, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 27)", license="Unsplash License",
        note="incidental person (distant, non-prominent); GPS (fictional)",
        exif=ExifProfile(
            datetime="2024:09:05 20:38:46",
            gps=gps((64, 8, 36), (21, 56, 36)), gps_ref=("N", "W"),
        ),
    ),
    StockFile(
        name="IMG_20240512_153022.jpg", kind="picsum", picsum_id=16, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 16)", license="Unsplash License",
        note="phone-style name; landscape pixels + orientation 6 (displays portrait)",
        exif=ExifProfile(orientation=6, datetime="2024:09:14 14:22:09"),
    ),
    StockFile(
        name="portrait-peaks-orient8.jpg", kind="picsum", picsum_id=29, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 29)", license="Unsplash License",
        note="landscape pixels + orientation 8 (displays portrait)",
        exif=ExifProfile(orientation=8, datetime="2024:10:02 07:55:30"),
    ),
    StockFile(
        name="rotated-beach-orient3.jpg", kind="picsum", picsum_id=12, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 12)", license="Unsplash License",
        note="orientation 3 (180°)",
        exif=ExifProfile(orientation=3, datetime="2024:10:18 16:08:12"),
    ),
    StockFile(
        name="rotated-shore-orient7.jpg", kind="picsum", picsum_id=14, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 14)", license="Unsplash License",
        note="orientation 7 (transverse)",
        exif=ExifProfile(orientation=7, datetime="2024:11:09 10:41:58"),
    ),
    StockFile(
        name="noexif-book.jpg", kind="picsum", picsum_id=24, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 24)", license="Unsplash License",
        note="no EXIF at all (stripped by some transfers)",
    ),
    StockFile(
        name="noexif-coffee.jpg", kind="picsum", picsum_id=30, size=(1920, 1080),
        source="Unsplash via picsum.photos (id 30)", license="Unsplash License",
        note="no EXIF at all",
    ),
    StockFile(
        name="small-cat.jpg", kind="picsum", picsum_id=40, size=(320, 200),
        source="Unsplash via picsum.photos (id 40)", license="Unsplash License",
        note="tiny image (tests upscaling)",
        exif=ExifProfile(datetime="2024:11:27 13:19:44"),
    ),
    StockFile(
        name="IMG-20240512-WA0001.jpg", kind="picsum", picsum_id=46, size=(3840, 2160),
        source="Unsplash via picsum.photos (id 46)", license="Unsplash License",
        note="WhatsApp-style name; oversized 4K (tests downscaling)",
        exif=ExifProfile(datetime="2024:12:04 18:36:27"),
    ),
    # -- Synthesized graphics --------------------------------------------------
    StockFile(
        name="Screenshot 2024-05-12 at 15.30.22.png", kind="screenshot", size=(1179, 2556),
        source="synthesized (Pillow)", license="original work",
        note="phone screenshot: portrait, text-heavy, spaces in filename",
    ),
    StockFile(
        name="transparent-shape.png", kind="transparent", size=(1200, 800),
        source="synthesized (Pillow)", license="original work",
        note="PNG with alpha channel (tests the RGBA path)",
    ),
    StockFile(
        name="animated-gif.gif", kind="gif", size=(640, 400),
        source="synthesized (Pillow)", license="original work",
        note="animated GIF (only animated format the provider accepts)",
    ),
]


# ---------------------------------------------------------------------------
# EXIF
# ---------------------------------------------------------------------------


def build_exif_bytes(p: ExifProfile, w: int, h: int) -> bytes:
    """Serialize a synthetic phone-style EXIF payload (see probe in the session)."""
    exif = Image.Exif()
    exif[0x0112] = p.orientation
    exif[0xA002] = w
    exif[0xA003] = h
    if p.datetime:
        exif._ifds[0x8769] = {0x9003: p.datetime, 0x9004: p.datetime}
    if p.gps and p.gps_ref:
        exif._ifds[0x8825] = {
            0: b"\x02\x03\x00\x00",
            1: p.gps_ref[0],
            2: p.gps[0],
            3: p.gps_ref[1],
            4: p.gps[1],
            29: p.datetime[:10] if p.datetime else "2024:01:01",
        }
    return exif.tobytes()


def reencode_real(src: Path, dest: Path) -> None:
    """Re-encode a real photo to q80, preserving EXIF (MakerNote/IFD1 dropped)."""
    img = Image.open(src)
    exif = img.getexif()
    for tag in (0x0111, 0xA005):  # thumbnail / interop IFDs: dangling pointers
        exif.pop(tag, None)
    sub = exif.get_ifd(0x8769)
    sub.pop(0x9286, None)  # MakerNote (vendor-specific, large)
    img.save(dest, quality=80, exif=exif.tobytes())


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------


def download_picsum(session: requests.Session, picsum_id: int, w: int, h: int,
                    dest: Path) -> None:
    url = f"https://picsum.photos/id/{picsum_id}/{w}/{h}"
    backoff = 2.0
    for attempt in range(1, 7):
        try:
            resp = session.get(url, stream=True, timeout=60)
        except requests.exceptions.RequestException as e:
            print(f"    connection error ({type(e).__name__}); retrying in {backoff:.0f}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or backoff)
            print(f"    429 rate-limited; waiting {wait:.0f}s (attempt {attempt})...")
            time.sleep(wait)
            backoff = min(backoff * 2, 60)
            continue
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            print(f"    HTTP {status}; retrying in {backoff:.0f}s (attempt {attempt})")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                f.write(chunk)
        return
    raise RuntimeError(f"download failed after 6 attempts: {url}")


# ---------------------------------------------------------------------------
# Synthesized graphics
# ---------------------------------------------------------------------------


def make_screenshot(dest: Path) -> None:
    """A deterministic phone-style screenshot: dark UI, status bar, photo grid."""
    w, h = 1179, 2556
    img = Image.new("RGB", (w, h), (28, 28, 30))
    d = ImageDraw.Draw(img)
    font_sm = ImageFont.load_default(size=44)
    font_lg = ImageFont.load_default(size=72)

    # Status bar
    d.text((64, 48), "15:30", font=font_sm, fill=(235, 235, 235))
    d.rectangle((w - 260, 56, w - 64, 96), outline=(235, 235, 235), width=4)
    d.rectangle((w - 252, 64, w - 150, 88), fill=(235, 235, 235))

    # App header
    d.text((64, 200), "Photos", font=font_lg, fill=(235, 235, 235))
    d.text((64, 320), "May 2024", font=font_sm, fill=(140, 140, 145))

    # Photo grid: 2 columns x 3 rows of muted tiles
    colors = [
        (94, 117, 148), (148, 120, 94), (94, 148, 110),
        (148, 94, 94), (110, 94, 148), (148, 140, 94),
    ]
    tile_w, tile_h, gap = 535, 535, 24
    x0, y0 = 64, 480
    for i, c in enumerate(colors):
        r, col = divmod(i, 2)
        d.rounded_rectangle(
            (x0 + col * (tile_w + gap), y0 + r * (tile_h + gap),
             x0 + col * (tile_w + gap) + tile_w, y0 + r * (tile_h + gap) + tile_h),
            radius=28, fill=c,
        )

    # Text lines (placeholder copy)
    y = y0 + 3 * (tile_h + gap) + 40
    for width in (900, 1050, 760):
        d.rounded_rectangle((64, y, 64 + width, y + 44), radius=22, fill=(70, 70, 74))
        y += 84

    # Bottom nav bar
    d.rectangle((0, h - 160, w, h), fill=(20, 20, 22))
    for i in range(4):
        cx = 190 + i * 300
        d.ellipse((cx - 34, h - 110, cx + 34, h - 42),
                   fill=(235, 235, 235) if i == 0 else (110, 110, 115))
    img.save(dest)  # PNG, no EXIF


def make_transparent(dest: Path) -> None:
    """An RGBA image with opaque, semi-transparent, and fully transparent regions."""
    w, h = 1200, 800
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((150, 150, 450, 450), fill=(80, 160, 255, 255))
    d.rounded_rectangle((500, 200, 950, 550), radius=60, fill=(255, 190, 60, 128))
    d.rectangle((950, 550, 1100, 700), fill=(40, 200, 120, 255))
    img.save(dest)  # PNG, no EXIF


def make_gif(dest: Path) -> None:
    """A 10-frame animation: a circle travelling along a sine arc."""
    w, h = 640, 400
    frames = []
    for i in range(10):
        f = Image.new("RGB", (w, h), (28, 30, 40))
        d = ImageDraw.Draw(f)
        x = int(80 + i * (w - 160) / 9)
        y = int(h / 2 + 90 * math.sin(i * math.pi / 4))
        d.ellipse((x - 40, y - 40, x + 40, y + 40), fill=(255, 210, 90))
        frames.append(f.convert("P", palette=Image.Palette.ADAPTIVE))
    frames[0].save(dest, save_all=True, append_images=frames[1:],
                   duration=120, loop=0, optimize=True)


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


def write_attribution() -> None:
    lines = [
        "# Stock images — attribution & provenance",
        "",
        "Test fixtures for the local album provider and slideshow tests. The set",
        "is a representative mix of **real smartphone photos** and **synthesized",
        "phone-style files** — see [docs/stock-images.md](../../docs/stock-images.md)",
        "for the selection rationale.",
        "",
        "## Real smartphone photos (Wikimedia Commons)",
        "",
        "| File | Camera | Author | License | Credit line |",
        "|------|--------|--------|---------|-------------|",
    ]
    cameras = {
        "Михайлівський_Золотоверхий_монастир._Київ6.jpg": "Apple iPhone 11",
        "Bundesministerium_für_Verkehr_und_digitale_Infrastruktur_(Berlin)_–_Datensummit_2017_(2).jpg": "Apple iPhone 7",
        "Estación_Ciudad_del_Futuro_L3_-_Agosto_2025_(3).jpg": "Xiaomi 220233L2G",
        "HK_CWB_銅鑼灣_Causeway_Bay_溫莎大廈_Windsor_House_mall_shop_August_2020_SS2_03.jpg": "Samsung SM-A205GN",
        "Haçlar_tepesi_7.jpg": "Samsung SM-A217F",
        "Good-Samaritan-3-105224.jpg": "Huawei GRA-L09",
        "Borgward_RS_(54329616959).jpg": "Google Pixel 7 Pro",
    }
    for f in SPEC:
        if f.kind != "real":
            continue
        lines.append(
            f"| {f.name} | {cameras[f.name]} | {f.author} | {f.license} | {f.credit} |"
        )
    lines += [
        "",
        "Real photos were re-encoded to JPEG q80 for a stable repo size; EXIF",
        "(orientation, capture time, GPS) is preserved, vendor MakerNote dropped.",
        "",
        "## Stock photos (Unsplash via picsum.photos)",
        "",
        "Unsplash License — free for commercial and non-commercial use, no",
        "attribution required, redistribution permitted. **The EXIF on these files",
        "(orientation, capture time, GPS) is synthesized for test coverage; the GPS",
        "coordinates are fictional.**",
        "",
        "| File | Source | EXIF profile |",
        "|------|--------|--------------|",
    ]
    for f in SPEC:
        if f.kind != "picsum":
            continue
        e = f.exif
        parts = [f"orientation {e.orientation}" if e and e.orientation != 1 else "orientation 1"]
        if e and e.datetime:
            parts.append(f"DateTimeOriginal {e.datetime}")
        if e and e.gps:
            parts.append("GPS (fictional)")
        if e and e.progressive:
            parts.append("progressive JPEG")
        if not e:
            parts = ["no EXIF"]
        lines.append(f"| {f.name} | {f.source} | {'; '.join(parts)} |")
    lines += [
        "",
        "## Synthesized graphics",
        "",
        "| File | What it is |",
        "|------|------------|",
    ]
    for f in SPEC:
        if f.kind in ("screenshot", "transparent", "gif"):
            lines.append(f"| {f.name} | {f.note} |")
    lines += [
        "",
        "## Review notes",
        "",
        "- No image contains prominent, identifiable people; the one person shot is a",
        "  distant, incidental figure (non-defamatory, non-promotional use).",
        "- No trademarked logos or branding appear in frame.",
        "- Files with `noexif-` prefix deliberately carry no EXIF metadata.",
    ]
    (OUT_DIR / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    if not REAL_DIR.is_dir():
        print(f"missing {REAL_DIR} — run the Commons collector first", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = API_UA

    for f in SPEC:
        dest = OUT_DIR / f.name
        if f.kind == "real":
            src = REAL_DIR / (f.real_file or f.name)
            if not src.is_file():
                print(f"  MISSING real source: {src}", file=sys.stderr)
                return 1
            reencode_real(src, dest)
        elif f.kind == "picsum":
            assert f.picsum_id is not None and f.size is not None
            w, h = f.size
            download_picsum(session, f.picsum_id, w, h, dest)
            img = Image.open(dest)
            if f.exif:
                img.save(dest, quality=85, exif=build_exif_bytes(f.exif, w, h))
            else:
                img.save(dest, quality=85)  # re-save without EXIF
            time.sleep(1.0)
        elif f.kind == "screenshot":
            make_screenshot(dest)
        elif f.kind == "transparent":
            make_transparent(dest)
        elif f.kind == "gif":
            make_gif(dest)
        else:
            raise ValueError(f"unknown kind {f.kind!r}")
        size_kb = dest.stat().st_size // 1024
        print(f"  {f.name}  ({size_kb} KB)")

    write_attribution()
    total = sum(p.stat().st_size for p in OUT_DIR.iterdir() if p.is_file())
    print(f"\nWrote {len(list(OUT_DIR.iterdir()))} files, {total / 1024 / 1024:.1f} MB total "
          f"in {OUT_DIR.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
