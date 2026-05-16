"""Screenshot comparison utilities for Tier 3 integration tests."""
from pathlib import Path

import numpy as np
from PIL import Image

GOLDEN_DIR = Path(__file__).parent / "golden"


def assert_screenshot_matches(
    actual_path: Path | str,
    golden_name: str,
    threshold: float = 0.02,
    ignore_rects: list[tuple[int, int, int, int]] | None = None,
) -> None:
    """Fail if more than `threshold` fraction of pixels differ by >10 per channel.

    Parameters
    ----------
    actual_path:
        Path to the screenshot captured from the device.
    golden_name:
        Base filename (without extension) of the golden image in tests/golden/.
    threshold:
        Maximum fraction of differing pixels allowed (default 2%).
    ignore_rects:
        List of (x, y, w, h) regions blacked out before comparison (e.g. clock area).
    """
    actual_img = Image.open(actual_path).convert("RGB")
    actual = np.array(actual_img, dtype=int)

    golden_path = GOLDEN_DIR / f"{golden_name}.png"
    if not golden_path.exists():
        # First run — save this as the golden reference
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray(actual.astype("uint8")).save(golden_path)
        return

    golden = np.array(Image.open(golden_path).convert("RGB"), dtype=int)

    if actual.shape != golden.shape:
        raise AssertionError(
            f"{golden_name}: size mismatch — actual {actual.shape[:2]}, "
            f"golden {golden.shape[:2]}"
        )

    # Black out ignored regions in both images before comparison
    if ignore_rects:
        actual = actual.copy()
        golden = golden.copy()
        for x, y, w, h in ignore_rects:
            actual[y : y + h, x : x + w] = 0
            golden[y : y + h, x : x + w] = 0

    diff = np.abs(actual - golden)
    differing = float(np.mean(np.any(diff > 10, axis=2)))
    assert differing <= threshold, (
        f"{golden_name}: {differing:.1%} of pixels differ "
        f"(threshold {threshold:.1%}). "
        f"Delete tests/golden/{golden_name}.png to regenerate."
    )
