# Stock images — attribution & provenance

Test fixtures for the local album provider and slideshow tests. The set
is a representative mix of **real smartphone photos** and **synthesized
phone-style files** — see [docs/stock-images.md](../../docs/stock-images.md)
for the selection rationale.

## Real smartphone photos (Wikimedia Commons)

| File | Camera | Author | License | Credit line |
|------|--------|--------|---------|-------------|
| Михайлівський_Золотоверхий_монастир._Київ6.jpg | Apple iPhone 11 | Мандрівниця | CC BY-SA 4.0 | Author: Мандрівниця. License: CC BY-SA 4.0, via Wikimedia Commons. |
| Bundesministerium_für_Verkehr_und_digitale_Infrastruktur_(Berlin)_–_Datensummit_2017_(2).jpg | Apple iPhone 7 | ubahnverleih | CC0 | Author: ubahnverleih. CC0, via Wikimedia Commons. |
| Estación_Ciudad_del_Futuro_L3_-_Agosto_2025_(3).jpg | Xiaomi 220233L2G | José Chuito | CC BY 4.0 | Author: José Chuito. License: CC BY 4.0, via Wikimedia Commons. |
| HK_CWB_銅鑼灣_Causeway_Bay_溫莎大廈_Windsor_House_mall_shop_August_2020_SS2_03.jpg | Samsung SM-A205GN | Ahoi Yahgeum Windhuo | CC BY-SA 4.0 | Author: Ahoi Yahgeum Windhuo. License: CC BY-SA 4.0, via Wikimedia Commons. |
| Haçlar_tepesi_7.jpg | Samsung SM-A217F | Zemxer | CC BY-SA 4.0 | Author: Zemxer. License: CC BY-SA 4.0, via Wikimedia Commons. |
| Good-Samaritan-3-105224.jpg | Huawei GRA-L09 | Bukvoed | CC BY 4.0 | Author: Bukvoed. License: CC BY 4.0, via Wikimedia Commons. |
| Borgward_RS_(54329616959).jpg | Google Pixel 7 Pro | Thomas Vogt from Paderborn, Deutschland | CC BY 2.0 | Author: Thomas Vogt. License: CC BY 2.0, via Wikimedia Commons. |

Real photos were re-encoded to JPEG q80 for a stable repo size; EXIF
(orientation, capture time, GPS) is preserved, vendor MakerNote dropped.

## Stock photos (Unsplash via picsum.photos)

Unsplash License — free for commercial and non-commercial use, no
attribution required, redistribution permitted. **The EXIF on these files
(orientation, capture time, GPS) is synthesized for test coverage; the GPS
coordinates are fictional.**

| File | Source | EXIF profile |
|------|--------|--------------|
| landscape-valley.jpg | Unsplash via picsum.photos (id 11) | orientation 1; DateTimeOriginal 2024:05:12 15:30:22; progressive JPEG |
| landscape-santorini.jpg | Unsplash via picsum.photos (id 49) | orientation 1; DateTimeOriginal 2024:06:01 08:15:44; GPS (fictional) |
| street-european.jpg | Unsplash via picsum.photos (id 57) | orientation 1; DateTimeOriginal 2024:06:15 17:42:10 |
| night-bokeh.jpg | Unsplash via picsum.photos (id 56) | orientation 1; DateTimeOriginal 2024:07:03 23:12:05 |
| night-city-bw.jpg | Unsplash via picsum.photos (id 43) | orientation 1; DateTimeOriginal 2024:07:19 22:47:33 |
| highcontrast-heels.jpg | Unsplash via picsum.photos (id 21) | orientation 1; DateTimeOriginal 2024:08:08 11:24:51 |
| highcontrast-lighthouse-bw.jpg | Unsplash via picsum.photos (id 58) | orientation 1; DateTimeOriginal 2024:08:22 09:03:17 |
| people-cliff-sunset.jpg | Unsplash via picsum.photos (id 27) | orientation 1; DateTimeOriginal 2024:09:05 20:38:46; GPS (fictional) |
| IMG_20240512_153022.jpg | Unsplash via picsum.photos (id 16) | orientation 6; DateTimeOriginal 2024:09:14 14:22:09 |
| portrait-peaks-orient8.jpg | Unsplash via picsum.photos (id 29) | orientation 8; DateTimeOriginal 2024:10:02 07:55:30 |
| rotated-beach-orient3.jpg | Unsplash via picsum.photos (id 12) | orientation 3; DateTimeOriginal 2024:10:18 16:08:12 |
| rotated-shore-orient7.jpg | Unsplash via picsum.photos (id 14) | orientation 7; DateTimeOriginal 2024:11:09 10:41:58 |
| noexif-book.jpg | Unsplash via picsum.photos (id 24) | no EXIF |
| noexif-coffee.jpg | Unsplash via picsum.photos (id 30) | no EXIF |
| small-cat.jpg | Unsplash via picsum.photos (id 40) | orientation 1; DateTimeOriginal 2024:11:27 13:19:44 |
| IMG-20240512-WA0001.jpg | Unsplash via picsum.photos (id 46) | orientation 1; DateTimeOriginal 2024:12:04 18:36:27 |

## Synthesized graphics

| File | What it is |
|------|------------|
| Screenshot 2024-05-12 at 15.30.22.png | phone screenshot: portrait, text-heavy, spaces in filename |
| transparent-shape.png | PNG with alpha channel (tests the RGBA path) |
| animated-gif.gif | animated GIF (only animated format the provider accepts) |

## Review notes

- No image contains prominent, identifiable people; the one person shot is a
  distant, incidental figure (non-defamatory, non-promotional use).
- No trademarked logos or branding appear in frame.
- Files with `noexif-` prefix deliberately carry no EXIF metadata.
