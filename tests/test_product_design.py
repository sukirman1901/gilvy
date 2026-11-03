"""Inbox quality invariants: measured text, independent surfaces and real state changes."""

import copy

import numpy as np
import pytest

from gilvy.errors import GilvyError
from gilvy.product import ProductFilm, validate
from gilvy.product_design import (
    PARTS,
    TOKENS,
    _font,
    fit_text,
    inbox,
    inbox_part,
    wrap_text,
)


def test_long_localized_content_is_measured_and_parts_keep_native_bounds():
    name = "Nadia Putri Kusumawardhani dengan nama yang sangat panjang"
    fitted = fit_text(name, 160, 12, "Medium")
    assert fitted.endswith("…") and _font(12, "Medium").getlength(fitted) <= 320
    assert wrap_text("Halo Nadia, saya bantu cek pesanan Anda.", 180, 14) == [
        "Halo Nadia, saya bantu",
        "cek pesanan Anda.",
    ]
    content = {
        "customer": name,
        "email": "alamat-email-yang-sangat-panjang@example.test",
        "source_text": "Dokumentasi " + "panjang " * 60,
        "message": "pesanan " * 60,
    }
    for part, (_, _, w, h) in PARTS.items():
        image = inbox_part(part, content)
        assert image.size == (w, h) and image.mode == "RGBA"
    assert inbox(content).size == (1280, 760)


def test_reply_progress_survives_renderer_cache_and_send_changes_only_feedback():
    x, y, w, h = PARTS["reply"]
    spec = {
        "style": "product",
        "size": [472, 214],
        "fps": 10,
        "duration": 1,
        "layers": [
            {
                "id": "reply",
                "type": "inbox-part",
                "part": "reply",
                "width": w,
                "height": h,
                "x": w / 2,
                "y": h / 2,
                "keyframes": {"progress": [[0, 0], [1, 1, "linear"]]},
            }
        ],
    }
    film = ProductFilm(spec)
    a, b = np.array(film.frame(0)), np.array(film.frame(0.9))
    assert not np.array_equal(a[45:155], b[45:155])
    before = np.array(inbox_part("reply"))
    after = np.array(inbox_part("reply", {"sent": True}))
    assert np.array_equal(before[:170], after[:170])
    assert not np.array_equal(before[170:], after[170:])
    # Independent source appearance must not alter the static conversation.
    assert np.array_equal(
        np.array(inbox_part("thread", progress=0)),
        np.array(inbox_part("thread", progress=1)),
    )


def test_normal_text_tokens_have_contrast_on_their_actual_surfaces():
    def luminance(hex_color):
        rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * w for v, w in zip(rgb, (0.2126, 0.7152, 0.0722)))

    for foreground, background in (
        ("ink", "surface"),
        ("secondary", "surface"),
        ("muted", "sidebar"),
        ("blue", "selection"),
    ):
        a, b = sorted((luminance(TOKENS[foreground]), luminance(TOKENS[background])))
        assert (b + 0.05) / (a + 0.05) >= 4.5


@pytest.mark.parametrize(
    "content,part",
    [
        ({"sent": "yes"}, "reply"),
        ({"unknown": "value"}, "thread"),
        ({"customer": 12}, "customer"),
        ({}, "unknown"),
        ({}, []),
    ],
)
def test_invalid_inbox_content_is_rejected(content, part):
    spec = {
        "style": "product",
        "size": [160, 160],
        "duration": 1,
        "layers": [
            {
                "id": "part",
                "type": "inbox-part",
                "part": part,
                "content": content,
                "width": 100,
                "height": 100,
            }
        ],
    }
    with pytest.raises(GilvyError):
        validate(spec)
