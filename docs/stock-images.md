# Stock Images for Testing

Research on royalty-free image sources for a representative test set used by
the **local album provider** (`src/piframe/providers/local.py`) and the
slideshow/surface-cache tests.

## Requirements for the test set

Derived from the codebase and the product context:

- **The album hosts arbitrary user uploads, typically smartphone photos** —
  not professional camera shots. The set must be representative of phone
  photos (see [What a smartphone photo looks like](#what-a-smartphone-photo-looks-like)).
- **Formats:** the local provider scans `.jpg`, `.jpeg`, `.png`, `.gif`
  (`IMAGE_EXTENSIONS` in `src/piframe/image.py`).
- **Resolution:** the frame renders fullscreen at **1280×800** (Waveshare
  10.1" DSI LCD, see [hardware.md](hardware.md)). Photos downscaled to that
  size (plus a few portrait/small/oversized variants) keep the repo small.
- **Size budget:** the device is a 512 MB Pi 3A+ and the repo is rsynced to
  it — keep the committed set to roughly 10–20 files, ~1–3 MB each after
  downscaling (~20–40 MB total).
- **Licensing:** committing images to the repo is **redistribution**, so each
  source's license must permit redistribution. Attribution, where required,
  must be recorded in-repo (see [Attribution plan](#attribution-plan)).

## What a smartphone photo looks like

Phone photos carry properties that professional stock shots usually don't, and
each one exercises a different code path in the frame:

| Phone-photo property | Why it matters to the app |
|---|---|
| **EXIF orientation tag** — phone photos shot in portrait are stored as landscape pixels with a tag of 6 (or 8) | `PhotoCache` applies all 8 orientation transforms (SH-07, LLD §3.2); the set needs files with tags 2–8, especially 6 |
| **4:3 and 16:9 aspect ratios** — the dominant phone ratios; the screen is 16:10 | Neither matches the screen, so both the fit path (letterbox + blurred background) and the fill path (center crop) do real work |
| **High resolution** — 12–48 MP (e.g. 4032×3024, 8000×6000) | Exercises LANCZOS downscaling to 1280×800; keep committed copies at ~2–4 MP to bound repo size |
| **GPS + capture-time EXIF** — present in essentially every phone photo | The app reads the capture time (`exif.py`) and ignores GPS. Use **synthetic coordinates** — never real locations |
| **Progressive JPEG** — common phone encoding | Decoders handle it, but include a couple of files |
| **Screenshots** — PNG, portrait (e.g. 1179×2556), text-heavy | A distinct content class users actually drop into albums |
| **GIFs from social media** | The only animated format the provider accepts |
| **No EXIF at all** — stripped by some transfers | `load_exif()` must tolerate it; include a couple of EXIF-free files |
| **Messy filenames** — `IMG_20240512_153022.jpg`, `Screenshot 2024-05-12 at 15.30.22.png`, Unicode | Filenames flow into the surface-cache key (`path.stem`); include a few with spaces/Unicode |

**Sourcing these:** two complementary routes —

1. **Real phone photos from Wikimedia Commons** — many files are tagged
   "shot on iPhone/Pixel/Samsung" with the original EXIF (orientation, GPS,
   timestamp) intact; CC-licensed, so attribution via the file's credit line.
   Prefer shots without identifiable people (personality rights).
2. **Synthesized from stock photos** — take a Tier-1 stock photo, rotate the
   pixels 90°, write EXIF orientation 6 + a fake GPS block +
   `DateTimeOriginal`, rename to `IMG_*.jpg`. Deterministic, the license stays
   with the stock source, and there is zero privacy exposure.

**HEIC — open question.** The iPhone's default camera format is HEIC, which
the current extension filter (`.jpg/.jpeg/.png/.gif`) silently ignores. Most
users export JPEG when sharing, but whether the frame should decode HEIC (e.g.
via `pillow-heif`) or document it as unsupported is a product decision to make
before finalizing the set.

## Sources

### Tier 1 — no attribution required (cleanest for a repo)

| Source | License | Attribution | Notes |
|--------|---------|-------------|-------|
| **StockSnap.io** (stocksnap.io) | **CC0** — every image is governed exclusively by CC0 | None at all | The zero-obligation option: no credit, no restrictions beyond CC0. |
| **Unsplash** (unsplash.com) | **Unsplash License** | **Not required** for direct downloads (confirmed in Unsplash's help center, Aug 2025). *Exception:* the **Unsplash API** guidelines *do* require attributing Unsplash + the photographer with a link back — relevant only if we ever fetch via the API. | Best-in-class photo quality, ideal for a photo frame. Restrictions: no selling unaltered copies (prints/posters), no defamatory use of identifiable people, no implying endorsement, no building a competing image service. |
| **Pexels** (pexels.com) | **Pexels License** | Not required (appreciated) | Same restriction pattern as Unsplash (no unaltered resale, no defamation, no endorsement). |
| **Pixabay** (pixabay.com) | **Pixabay Content License** (some content is CC0) | Not required (appreciated) | Same restriction pattern; also has vectors/illustrations. |
| **NASA** (nasa.gov image library) | **Public domain** — US government works are "generally not subject to copyright in the United States" | Not legally required, but **NASA asks that it be acknowledged as the source** | Caveats: images with identifiable people need the person's permission for commercial use; NASA insignia/logotypes are protected; third-party copyrighted images are marked on the page. A non-promotional OSS test set is fine; avoid logo imagery. |
| **Burst by Shopify** (burst.shopify.com) | Burst free license | Not required | Free for commercial use, curated, good quality. |
| **GratisJPG / Gratisography** (gratisography.com) | Free Gratisography Photo License | Not required | Personal and commercial use, modification allowed; standard no-resale/no-endorsement restrictions. |

### Tier 2 — attribution required (manageable with a CREDITS file)

| Source | License | Attribution | Notes |
|--------|---------|-------------|-------|
| **Wikimedia Commons** (commons.wikimedia.org) | **Per-file**: CC0, CC BY, CC BY-SA, GFDL, public domain | **Required for CC BY / CC BY-SA** (creator name, license, link); recommended for PD/CC0 | Each file page has a ready-to-copy credit line. The Wikimedia Foundation gives **no warranty** on copyright status — verify each file. Non-copyright restrictions (trademarks, personality rights) can apply. Also the best source for **real smartphone photos** (many tagged "shot on iPhone/Pixel", EXIF intact). |
| **Openverse** (openverse.org) | Aggregator of CC-licensed and public-domain works (Flickr, Commons, …) | Depends on the item's license — **can be filtered to CC0 / public domain only**, which needs none | Has an API for programmatic fetching; the one-stop shop for "find me a CC0 photo of X". |
| **Flickr** (flickr.com, CC-licensed photos) | Per-photo CC license (CC0, CC BY, CC BY-SA, CC BY-NC, CC BY-ND) | **All CC licenses require attribution** (creator, license, source link) | Avoid **NC** (non-commercial) and **ND** (no derivatives) works for a repo. Flickr moved to CC 4.0 in 2025. |
| **Kaboompics** (kaboompics.com) | Free for personal and commercial use | **Required** — link back to the site | Some images are marked *Editorial Use Only* (no commercial use) — skip those. Good lifestyle/interior shots. |

### Tier 3 — convenience (programmatic fetching)

| Source | License | Attribution | Notes |
|--------|---------|-------------|-------|
| **picsum.photos** (Lorem Picsum) | Serves **Unsplash photos** over a trivial URL API (`https://picsum.photos/1280/800?blur=2`); the service itself is MIT-licensed code | Unsplash License rules apply — none for direct use | The easiest way to script a fixed set of downloads at exact sizes; stable image IDs. |

### Sources to avoid

- **Raw Pixel** (rawpixel.com) — the free tier is a *personal-use* license;
  commercial use requires a paid license. Not suitable for a repo.
- Anything marked **editorial use only**, **NC**, **ND**, or carrying
  **trademarked logos/branding** prominent in frame.

## Recommended approach

1. **Primary:** pull the bulk of the set from **Unsplash / Pexels / Pixabay**
   (best photo quality and subject variety for a frame) — no attribution
   required for direct downloads, and all three licenses permit redistribution.
   **StockSnap (CC0)** or **NASA (PD)** work if we want zero obligations
   whatsoever.
2. **Programmatic:** use **picsum.photos** URLs (Unsplash photos) for a
   reproducible download script, or the **Openverse API** filtered to CC0.
3. **Mix for test coverage** — representative of a phone-filled album (see
   [Attribution plan](#attribution-plan) for where the files live):
   - ~8–12 landscape `.jpg` (4:3 and 16:9, ~2–4 MP) — nature, city, people,
     night, high-contrast
   - 2–3 portrait `.jpg` **with EXIF orientation 6/8** (the classic phone
     portrait: landscape pixels + rotation tag)
   - 1–2 files with other orientation tags (2–5, 7)
   - 1 `.png` screenshot (portrait, text-heavy) and 1 `.png` with transparency
   - 1 animated `.gif`
   - 1 small (e.g. 320×200) and 1 oversized (e.g. 3840×2160) to test
     up/downscaling
   - 1–2 files with **no EXIF** and 1–2 with **GPS + timestamp EXIF**
     (synthetic coordinates)
   - 2–3 files with phone-style filenames (spaces, `IMG_*`, Unicode)

## Attribution plan

- Keep the set in `tests/fixtures/stock/` (path to be finalized with the
  implementation).
- Add **`tests/fixtures/stock/ATTRIBUTION.md`** listing, per file: source
  site, author/photographer, license name, and source URL.
  - Required by: CC BY / CC BY-SA (Wikimedia, Flickr, Kaboompics), and
    requested by NASA ("acknowledged as the source").
  - Good practice even for Unsplash/Pexels/Pixabay/CC0 (attribution is
    encouraged there, and it documents provenance if a license ever changes).
- Re-verify each file's license page **at download time** — licenses and
  per-file terms can change; the per-file record in ATTRIBUTION.md is the
  audit trail.

## Test image set

Built under `tests/fixtures/stock/` (26 files, ~14.6 MB total, with
`ATTRIBUTION.md` documenting every file's source, license, and credit):

- **7 real smartphone photos** from Wikimedia Commons (iPhone 11, iPhone 7,
  Xiaomi, Samsung A20s, Samsung A21, Huawei, Pixel 7 Pro) — CC BY /
  CC BY-SA / CC0, re-encoded to q80 with EXIF preserved (orientation, GPS,
  `DateTimeOriginal`; vendor MakerNote dropped for size).
- **15 Unsplash photos** via picsum.photos at target sizes, with
  **synthesized phone-style EXIF**: orientation tags 1/3/6/7/8, fictional
  GPS coordinates, `DateTimeOriginal`, progressive encoding — plus one
  EXIF-free file, one 320×200, and one 3840×2160.
- **3 synthesized graphics**: a phone-style screenshot PNG (1179×2556), a
  transparent PNG (1200×800 RGBA), and a 10-frame animated GIF (640×400).

Every file maps to a row of the matrix in
[What a smartphone photo looks like](#what-a-smartphone-photo-looks-like).
HEIC is deliberately absent (see the open question above).

**Rebuild:** the set is generated by the curation tools in `eng/fixtures/`
(`collect_stock_images.py` for the Commons photos, `build_stock_fixtures.py`
for the full set). Re-running the build script is idempotent; the collect
step needs network access to the Commons API.

## Sources consulted

- Unsplash License & help center (attribution guidance, API attribution
  guideline) — unsplash.com/license, help.unsplash.com (Aug 2025)
- Pexels License — pexels.com/license
- Pixabay Content License & license summary — pixabay.com/service/terms,
  pixabay.com/service/license-summary
- StockSnap license (CC0) — stocksnap.io/license
- NASA Images & Media Guidelines — nasa.gov/nasa-brand-center/images-and-media
- Wikimedia Commons "Reusing content outside Wikimedia" —
  commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia
- Openverse — openverse.org
- Flickr copyright licenses — flickrhelp.com
- Gratisography license — gratisography.com/license
- Burst by Shopify — shopify.com/stock-photos
- picsum.photos / Lorem Picsum — picsum.photos
