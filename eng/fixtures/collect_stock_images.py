#!/usr/bin/env python
"""Collect a random sample of smartphone photos from Wikimedia Commons.

One-off curation tool for the stock-image test set (see
docs/stock-images.md). Draws random file members of a Commons category
(e.g. ``Category:Taken_with_iPhone``) via the API's ``list=random``
endpoint, filters by license / size / resolution, downloads the original
files, verifies EXIF locally with Pillow, and writes an ``ATTRIBUTION.md``
plus a machine-readable ``manifest.json`` for curation.

Usage:
    .venv/bin/python eng/fixtures/collect_stock_images.py \
        --category "Category:Taken_with_iPhone" --count 12

Output lands in ``.pi/tmp/stock-images/`` (scratch space, not committed);
``build_stock_fixtures.py`` then turns the collected photos into the
committed fixture set.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PIL import Image as PilImage

REPO = Path(__file__).resolve().parents[2]

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "digital-frame stock-image collector "
    "(https://github.com/njurgens/digital-frame; test-fixture research) python-requests"
)
POLITE_DELAY_S = 0.5
DOWNLOAD_DELAY_S = 1.0
WIKILINK_RE = re.compile(r"^\[\[(?:[^|\]]*\|)?([^\]]+)\]\]$")
TAG_RE = re.compile(r"<[^>]+>")


def clean_wikilink(value: str | None) -> str:
    """Strip a ``[[target|label]]`` wikilink down to its label (or target)."""
    if not value:
        return ""
    value = value.strip()
    m = WIKILINK_RE.match(value)
    return (m.group(1) if m else value).strip()


def clean_html(value: str | None) -> str:
    """Strip HTML from an extmetadata value.

    Hidden ``<div>`` blocks (Wikidata annotations) are dropped *with* their
    content; any remaining tags are removed and entities unescaped.
    """
    if not value:
        return ""
    value = re.sub(r"<div[^>]*>.*?</div>", "", value, flags=re.DOTALL)
    return html_module.unescape(TAG_RE.sub("", value)).strip()


@dataclass
class Candidate:
    """One sampled Commons file: API metadata plus locally verified EXIF."""

    title: str
    url: str = ""
    artist: str = ""
    license: str = ""
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    api_datetime: str = ""
    api_gps: str = ""
    description: str = ""
    local_path: str = ""
    local_orientation: int | None = None
    local_gps: str = ""
    local_datetime: str | None = None
    local_camera: str = ""
    skipped: str = ""  # non-empty when the candidate was filtered out


def make_session() -> requests.Session:
    """Return a requests session with the collector's User-Agent header."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def draw_random_file(session: requests.Session, category: str) -> str | None:
    """Draw one random file member of ``category`` (None when empty)."""
    resp = session.get(
        API,
        params={
            "action": "query",
            "format": "json",
            "list": "random",
            "rnnamespace": 6,
            "rnunique": 1,
            "rncategory": category,
        },
        timeout=30,
    )
    resp.raise_for_status()
    for entry in resp.json().get("query", {}).get("random", []):
        return entry.get("title")
    return None


def fetch_imageinfo(session: requests.Session, titles: list[str]) -> dict[str, dict]:
    """Batch ``imageinfo`` lookups; returns ``{file title: info}``."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 25):
        resp = session.get(
            API,
            params={
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "titles": "|".join(titles[i : i + 25]),
            },
            timeout=30,
        )
        resp.raise_for_status()
        for page in resp.json().get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if info:
                out[page["title"]] = info
        time.sleep(POLITE_DELAY_S)
    return out


def gps_from_pillow(path: Path) -> str:
    """Return ``"lat, lon"`` from the file's GPS IFD, or ``""`` when absent."""
    try:
        with PilImage.open(path) as img:
            gps = img.getexif().get_ifd(0x8825)
        lat, lon = gps.get(2), gps.get(4)  # GPSLatitude, GPSLongitude

        def to_float(rationals: object) -> float:
            d, m, s = rationals  # type: ignore[misc]
            return float(Fraction(d)) + float(Fraction(m)) / 60 + float(Fraction(s)) / 3600

        if not lat or not lon:
            return ""
        return f"{to_float(lat):.5f}, {to_float(lon):.5f}"
    except Exception:
        return ""


def _clean_tag(value: object) -> str:
    """Normalise an EXIF tag value (bytes/str, NUL-padded) to a clean string."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).replace("\x00", "").strip()


def local_exif(path: Path) -> tuple[int | None, str, str | None, str]:
    """Read orientation, GPS, DateTimeOriginal, and camera Make/Model from the file."""
    try:
        with PilImage.open(path) as img:
            exif = img.getexif()
            orientation = int(exif.get(0x0112) or 0) or None
            sub = exif.get_ifd(0x8769)
            stamp = sub.get(0x9003)
            dt = str(stamp).strip() if stamp else None
            make = _clean_tag(exif.get(0x010F))
            model = _clean_tag(exif.get(0x0110))
        return orientation, gps_from_pillow(path), dt, f"{make} {model}".strip()
    except Exception:
        return None, "", None, ""


def credit_line(artist: str, license: str) -> str:
    """Format the attribution credit line for a file."""
    if not license or "public domain" in license.lower():
        return f"Author: {artist or 'unknown'}. Public Domain, via Wikimedia Commons."
    return f"Author: {artist or 'unknown'}. License: {license}, via Wikimedia Commons."


def human_size(n: int) -> str:
    """Format a byte count as a human-readable megabyte string."""
    return f"{n / 1024 / 1024:.1f} MB"


def download(session: requests.Session, url: str, dest: Path) -> None:
    """Stream ``url`` to ``dest``, retrying with backoff on 429s and connection errors."""
    backoff = 2.0
    for attempt in range(1, 7):
        try:
            resp = session.get(url, stream=True, timeout=60)
        except requests.exceptions.RequestException as e:
            wait = backoff
            print(
                f"    connection error ({type(e).__name__}); "
                f"waiting {wait:.0f}s (attempt {attempt})..."
            )
            time.sleep(wait)
            backoff = min(backoff * 2, 60)
            continue
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or backoff)
            print(f"    429 rate-limited; waiting {wait:.0f}s (attempt {attempt})...")
            time.sleep(wait)
            backoff = min(backoff * 2, 60)
            continue
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                f.write(chunk)
        return
    raise RuntimeError(f"download failed after 6 attempts: {url}")


def main() -> int:
    """Collect a random sample of smartphone photos from Wikimedia Commons."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category",
        default="Category:Taken_with_iPhone",
        help="comma-separated list of Commons categories to draw from",
    )
    parser.add_argument("--count", type=int, default=12, help="files to keep (default 12)")
    parser.add_argument("--out", default=str(REPO / ".pi" / "tmp" / "stock-images"))
    parser.add_argument("--min-mb", type=float, default=0.5)
    parser.add_argument("--max-mb", type=float, default=20.0)
    parser.add_argument("--min-px", type=int, default=1500, help="min longest side")
    parser.add_argument("--max-px", type=int, default=12000)
    parser.add_argument(
        "--extensions", default=".jpg,.jpeg", help="comma list of allowed file extensions"
    )
    parser.add_argument(
        "--camera",
        default="",
        help="case-insensitive regex the EXIF camera Make/Model must match "
        "(e.g. 'iphone|pixel|galaxy'); non-matching downloads are discarded",
    )
    parser.add_argument(
        "--max-downloads",
        type=int,
        default=0,
        help="download budget (default: 4x --count); bounds 429 exposure when filtering by camera",
    )
    parser.add_argument("--dry-run", action="store_true", help="filter only; no downloads")
    parser.add_argument(
        "--allow-no-exif",
        action="store_true",
        help="keep files without an EXIF capture time (default: skip them — "
        "real camera files carry one)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    exts = {e.strip().lower() for e in args.extensions.split(",")}

    # 1. Draw a pool of random candidates (extra headroom for filtering;
    #    the camera filter needs a lot more headroom since most files in
    #    per-model categories are mislabeled).
    categories = [c.strip() for c in args.category.split(",") if c.strip()]
    camera_re = re.compile(args.camera, re.IGNORECASE) if args.camera else None
    pool_size = args.count * (10 if camera_re else 3)
    pool: list[str] = []
    seen: set[str] = set()
    draws, max_draws = 0, pool_size * 3
    while len(pool) < pool_size and draws < max_draws:
        draws += 1
        title = draw_random_file(session, random.choice(categories))
        if not title or title in seen:
            continue
        seen.add(title)
        pool.append(title)
    print(f"Drew {len(pool)} unique candidates from {len(categories)} categories in {draws} draws")
    if not pool:
        print("Category is empty or unreachable — nothing to do.", file=sys.stderr)
        return 1

    # 2. Fetch metadata for the whole pool in batched calls.
    infos = fetch_imageinfo(session, pool)

    # 3. Filter: extension, license, size, resolution.
    candidates: list[Candidate] = []
    for title in pool:
        info = infos.get(title, {})
        em = info.get("extmetadata", {})
        url = info.get("url", "")
        ext = Path(unquote(urlparse(url).path)).suffix.lower()
        c = Candidate(
            title=title,
            url=url,
            artist=clean_html(clean_wikilink(em.get("Artist", {}).get("value"))),
            license=em.get("LicenseShortName", {}).get("value", ""),
            size_bytes=int(info.get("size", 0)),
            width=int(info.get("width", 0)),
            height=int(info.get("height", 0)),
            api_datetime=clean_html(em.get("DateTimeOriginal", {}).get("value")),
            api_gps=clean_html(em.get("GPSPosition", {}).get("value")),
            description=clean_html(em.get("ImageDescription", {}).get("value")),
        )
        if ext not in exts:
            c.skipped = f"extension {ext or '(none)'} not allowed"
        elif not args.allow_no_exif and not c.api_datetime:
            c.skipped = "no EXIF capture time (not a real camera file)"
        elif "NC" in c.license.upper() or "ND" in c.license.upper():
            c.skipped = f"license {c.license!r} is non-commercial/no-derivatives"
        elif not (args.min_mb * 1e6 <= c.size_bytes <= args.max_mb * 1e6):
            c.skipped = f"size {human_size(c.size_bytes)} outside range"
        elif not (args.min_px <= max(c.width, c.height) <= args.max_px):
            c.skipped = f"longest side {max(c.width, c.height)} px outside range"
        candidates.append(c)

    kept = [c for c in candidates if not c.skipped]
    dropped = [c for c in candidates if c.skipped]
    print(f"{len(kept)} candidates passed metadata filters ({len(dropped)} filtered out)")
    for c in dropped:
        print(f"  - {c.title}: {c.skipped}")
    if not kept:
        print(
            "No candidates survived the filters — widen --min-px/--max-mb and retry.",
            file=sys.stderr,
        )
        return 1

    # 4. Download and verify EXIF locally. With --camera, non-matching files
    #    are discarded (the only reliable smartphone check is the file's own
    #    EXIF Make/Model — category tags are unreliable).
    max_downloads = args.max_downloads or args.count * 4
    kept_files: list[Candidate] = []
    rejected: list[Candidate] = []
    downloads = 0
    for c in kept:
        if len(kept_files) >= args.count or downloads >= max_downloads:
            break
        name = unquote(urlparse(c.url).path).rsplit("/", 1)[-1]
        c.local_path = str(images_dir / name)
        if args.dry_run:
            kept_files.append(c)
            continue
        downloads += 1
        download(session, c.url, images_dir / name)
        c.local_orientation, c.local_gps, c.local_datetime, c.local_camera = local_exif(
            images_dir / name
        )
        time.sleep(DOWNLOAD_DELAY_S)
        if camera_re and not camera_re.search(c.local_camera):
            c.skipped = f"camera {c.local_camera or 'unknown'} does not match --camera"
            (images_dir / name).unlink(missing_ok=True)
            rejected.append(c)
            print(f"  [x] {name}  camera={c.local_camera or '—'}  (discarded)")
            continue
        kept_files.append(c)
        print(
            f"  [{len(kept_files)}/{args.count}] {name}  {c.license or 'license?'}  "
            f"{c.width}x{c.height}  {human_size(c.size_bytes)}  camera={c.local_camera or '—'}"
        )
    kept = kept_files
    print(f"Kept {len(kept)} of {downloads} downloads ({len(rejected)} rejected by camera filter)")
    if not kept:
        print(
            "No files matched the filters — try more categories or a wider --camera regex.",
            file=sys.stderr,
        )
        return 1

    # 5. Write ATTRIBUTION.md + manifest.json.
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cats = ", ".join(f"[`{c}`](https://commons.wikimedia.org/wiki/{c})" for c in categories)
    lines = [
        "# Stock image attribution",
        "",
        f"Random sample of **{len(kept)}** files from {cats} "
        f"(Wikimedia Commons), collected {now}.",
        "",
        "> **Review before committing:** check each image for identifiable people,",
        "> trademarks, and sensitive content. Keep the credit lines below verbatim in",
        "> the repo's attribution file.",
        "",
        "| # | File | Author | License | Size | W×H | Camera | EXIF orient | GPS | Captured |",  # noqa: RUF001
        "|---|------|--------|---------|------|-----|--------|-------------|-----|----------|",
    ]
    for i, c in enumerate(kept, 1):
        name = Path(c.local_path).name if c.local_path else c.title
        orient = (
            ("—" if c.local_orientation is None else c.local_orientation)
            if not args.dry_run
            else "—"
        )
        gps = (c.local_gps or c.api_gps or "—") if not args.dry_run else (c.api_gps or "—")
        camera = (c.local_camera or "—") if not args.dry_run else "—"
        dt = c.local_datetime or c.api_datetime or "—"
        lines.append(
            f"| {i} | {name} | {c.artist or '—'} | {c.license or '—'} "
            f"| {human_size(c.size_bytes)} | {c.width}×{c.height} "  # noqa: RUF001
            f"| {camera} | {orient} | {gps} | {dt} |"
        )
    lines += ["", "## Credit lines", ""]
    for i, c in enumerate(kept, 1):
        name = Path(c.local_path).name if c.local_path else c.title
        lines.append(
            f"{i}. **{name}** — {credit_line(c.artist, c.license)} "
            f"Source: https://commons.wikimedia.org/wiki/{c.title}"
        )
    (out_dir / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "categories": categories,
        "camera_filter": args.camera,
        "collected": now,
        "draws": draws,
        "downloads": downloads,
        "dry_run": args.dry_run,
        "files": [asdict(c) for c in kept],
        "rejected": [asdict(c) for c in rejected],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {out_dir / 'ATTRIBUTION.md'} and {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
