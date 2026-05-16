import os
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.widgets.confirm_dialog import ConfirmDialog
from piframe.widgets.segmented_control import SegmentedControl
from piframe.widgets.toggle import Toggle
from piframe.widgets.vertical_slider import VerticalSlider


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def _mock_assets():
    assets = MagicMock()
    surf = pygame.Surface((60, 20))
    assets.font.return_value.render.return_value = (surf, pygame.Rect(0, 0, 60, 20))
    assets.font_bold.return_value.render.return_value = (surf, pygame.Rect(0, 0, 60, 20))
    return assets


def pixel_mean(surface, rect):
    sub = surface.subsurface(rect)
    arr = pygame.surfarray.array3d(sub)
    return arr.mean(axis=(0, 1))


def test_toggle_on_thumb_on_right():
    surf = pygame.Surface((50, 28))
    surf.fill((0, 0, 0))
    toggle = Toggle(rect=pygame.Rect(0, 0, 50, 28), initial=True)
    toggle.draw(surf)
    left_mean = pixel_mean(surf, pygame.Rect(0, 2, 20, 24))
    right_mean = pixel_mean(surf, pygame.Rect(28, 2, 20, 24))
    assert right_mean.mean() > left_mean.mean()


def test_toggle_off_thumb_on_left():
    surf = pygame.Surface((50, 28))
    surf.fill((128, 128, 128))
    toggle = Toggle(rect=pygame.Rect(0, 0, 50, 28), initial=False)
    toggle.draw(surf)
    left_mean = pixel_mean(surf, pygame.Rect(2, 2, 20, 24))
    right_mean = pixel_mean(surf, pygame.Rect(28, 2, 20, 24))
    assert left_mean.mean() > right_mean.mean()


def test_vertical_slider_at_100_thumb_near_top():
    surf = pygame.Surface((40, 200))
    surf.fill((0, 0, 0))
    slider = VerticalSlider(rect=pygame.Rect(0, 0, 40, 200), initial_value=100)
    slider.draw(surf)
    top_mean = pixel_mean(surf, pygame.Rect(0, 0, 40, 40))
    bottom_mean = pixel_mean(surf, pygame.Rect(0, 160, 40, 40))
    assert top_mean.mean() > bottom_mean.mean()


def test_vertical_slider_at_0_thumb_near_bottom():
    surf = pygame.Surface((40, 200))
    surf.fill((0, 0, 0))
    slider = VerticalSlider(rect=pygame.Rect(0, 0, 40, 200), initial_value=0)
    slider.draw(surf)
    top_mean = pixel_mean(surf, pygame.Rect(0, 0, 40, 40))
    bottom_mean = pixel_mean(surf, pygame.Rect(0, 160, 40, 40))
    assert bottom_mean.mean() > top_mean.mean()


def test_segmented_control_active_segment_filled():
    surf = pygame.Surface((300, 44))
    surf.fill((20, 20, 20))
    seg = SegmentedControl(
        rect=pygame.Rect(0, 0, 300, 44),
        segments=["A", "B", "C"],
        selected=1,
        assets=_mock_assets(),
    )
    seg.draw(surf)
    left_mean = pixel_mean(surf, pygame.Rect(5, 4, 90, 36))
    mid_mean = pixel_mean(surf, pygame.Rect(105, 4, 90, 36))
    assert mid_mean.mean() > left_mean.mean()


def test_confirm_dialog_scrim_drawn():
    surf = pygame.Surface((1280, 800))
    surf.fill((255, 255, 255))
    dlg = ConfirmDialog(
        title="Delete?",
        body="This cannot be undone.",
        on_confirm=lambda: None,
        on_cancel=lambda: None,
        assets=_mock_assets(),
    )
    dlg.draw(surf)
    corner_mean = pixel_mean(surf, pygame.Rect(0, 0, 50, 50))
    assert corner_mean.mean() < 255


def test_confirm_dialog_confirm_button_region():
    surf = pygame.Surface((1280, 800))
    surf.fill((40, 40, 40))
    dlg = ConfirmDialog(
        title="Delete?",
        body="This cannot be undone.",
        destructive=True,
        on_confirm=lambda: None,
        on_cancel=lambda: None,
        assets=_mock_assets(),
    )
    dlg.draw(surf)
    btn_mean = pixel_mean(surf, pygame.Rect(664, 452, 100, 44))
    assert btn_mean[0] > btn_mean[2]
