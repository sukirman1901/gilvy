"""Original 95s fictional SaaS launch film. No assets/audio from Numtera.

Run from an installed checkout: python examples/product/launch/build.py --out out/launch --render
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from gilvy.product import ProductFilm, load_product
from gilvy.product_design import Surface, PARTS, inbox_part, TOKENS
from gilvy.product_render import render_product

DURATIONS = [5, 4, 3, 4, 6, 6, 6, 4, 5, 5, 4, 5, 4, 4, 5, 7, 4, 4, 4, 3, 3]
NAMES = [
    "Masalah",
    "Pengulangan",
    "Cukup",
    "Perkenalan",
    "Inbox",
    "Percakapan",
    "Pencarian sumber",
    "Persetujuan",
    "Proses belajar",
    "Pengetahuan baru",
    "Dapat digunakan kembali",
    "Pertanyaan berikutnya",
    "Menentukan alur",
    "Navigasi workflow",
    "Konfigurasi",
    "Menyusun workflow",
    "Menyimpan",
    "Daftar workflow",
    "Manfaat",
    "Merek",
    "Penutup",
]
BLUE = "#2864e9"
INK = "#202631"
MUTED = "#667181"


def assets(root):
    root.mkdir(parents=True, exist_ok=True)
    for part in PARTS:
        inbox_part(part, {"brand": "ruang", "workspace": "Support workspace"}).save(
            root / f"{part}.png"
        )
    for sent in (False, True):
        inbox_part("reply", {"brand": "ruang", "sent": sent}).save(
            root / f"reply-{sent}.png"
        )
    s = Surface((0, 0, 620, 430))
    s.rect((0, 0, 619, 429), "#ffffff", 12, TOKENS["border"])
    s.icon("book", 26, 25, 20, BLUE)
    s.text(59, 27, "Knowledge search", 18, weight="SemiBold")
    s.rect((24, 75, 596, 121), "#f7f9fc", 8, TOKENS["border"])
    s.icon("search", 39, 91, 17, MUTED)
    s.text(69, 91, "Berapa lama pengiriman reguler?", 14)
    s.rect((24, 146, 596, 350), "#f8fbff", 9, "#dce7fc")
    s.rect((43, 165, 174, 191), "#edf7f0", 5)
    s.icon("check", 52, 171, 14, "#167451")
    s.text(74, 172, "Verified source", 10, "#167451", "Medium")
    s.text(43, 211, "Pengiriman reguler", 22, weight="SemiBold")
    s.paragraph(
        43,
        253,
        "Pesanan dikirim dalam 1 hari kerja setelah pembayaran. Estimasi tiba 2–3 hari kerja, bergantung pada tujuan.",
        522,
        15,
        max_lines=3,
        line_height=26,
    )
    s.text(25, 384, "Pusat bantuan / Pengiriman", 12, MUTED)
    s.text(478, 384, "Buka sumber", 12, BLUE, "Medium")
    s.im.save(root / "source.png")
    s = Surface((0, 0, 720, 400))
    s.rect((0, 0, 719, 399), "white", 12, TOKENS["border"])
    s.rect((24, 24, 66, 66), "#eef4ff", 10)
    s.icon("book", 35, 35, 20, BLUE)
    s.text(83, 29, "Knowledge unit created", 19, weight="SemiBold")
    s.text(83, 56, "Siap digunakan oleh seluruh tim", 12, MUTED)
    s.line([(24, 91), (696, 91)])
    s.text(32, 118, "Estimasi pengiriman", 26, weight="Medium")
    s.paragraph(
        32,
        165,
        "Jawaban yang sudah diperiksa menjadi pengetahuan bersama. Lengkap dengan sumber dan konteks percakapannya.",
        650,
        16,
        max_lines=3,
        line_height=28,
    )
    for i, (a, b) in enumerate(
        [
            ("Sumber", "Panduan pengiriman"),
            ("Status", "Terverifikasi"),
            ("Diperbarui", "Baru saja"),
        ]
    ):
        y = 274 + i * 34
        s.text(32, y, a, 12, MUTED)
        s.text(240, y, b, 13, "#167451" if i == 1 else INK, "Medium")
    s.im.save(root / "knowledge-card.png")
    # A coherent workflow editor, assembled as independently animated planes.
    for saved in (False, True):
        s = Surface((0, 0, 1000, 620))
        s.rect((0, 0, 999, 619), "white", 12, TOKENS["border"])
        s.text(26, 24, "ruang", 21, weight="SemiBold")
        s.text(118, 29, "/ Workflows / Informasi pengiriman", 13, MUTED)
        s.rect((829, 18, 975, 56), "#edf7f0" if saved else BLUE, 7)
        s.icon(
            "check" if saved else "plus", 842, 30, 14, "#167451" if saved else "white"
        )
        s.text(
            865,
            31,
            "Tersimpan" if saved else "Simpan alur",
            12,
            "#167451" if saved else "white",
            "Medium",
        )
        s.line([(0, 76), (1000, 76)])
        s.rect((0, 77, 225, 619), "#f9fafc", 0)
        s.line([(225, 76), (225, 620)])
        s.text(24, 105, "Informasi pengiriman", 15, weight="SemiBold", width=184)
        s.text(24, 135, "WORKFLOW", 10, MUTED, "Medium")
        for i, (icon, label) in enumerate(
            [("flow", "Editor"), ("chart", "Activity"), ("settings", "Settings")]
        ):
            y = 181 + i * 43
            if i == 0:
                s.rect((12, y - 10, 213, y + 29), "#eef4ff", 7)
            s.icon(icon, 25, y, 16, BLUE if i == 0 else MUTED)
            s.text(54, y + 1, label, 13, BLUE if i == 0 else MUTED)
        s.text(24, 530, "Sumber terhubung", 11, MUTED)
        s.icon("book", 24, 560, 16, BLUE)
        s.text(50, 562, "Panduan pengiriman", 11)
        s.text(259, 105, "Bangun jawaban yang konsisten", 21, weight="SemiBold")
        s.text(259, 139, "Tiga langkah. Satu alur yang dapat dipakai lagi.", 12, MUTED)
        s.im.save(root / f"workflow-frame-{saved}.png")
    for i, (label, title, desc) in enumerate(
        [
            ("TRIGGER", "Pertanyaan masuk", "Pesan baru tentang estimasi pengiriman"),
            ("KNOWLEDGE", "Temukan jawaban", "Gunakan sumber yang sudah diverifikasi"),
            (
                "RESPONSE",
                "Kirim respons",
                "Jawaban konsisten, dengan konteks yang tepat",
            ),
        ]
    ):
        s = Surface((0, 0, 690, 116))
        s.rect((0, 0, 689, 115), "white", 10, TOKENS["border"])
        s.rect((20, 20, 58, 58), "#edf3ff", 9)
        s.icon(["inbox", "book", "send"][i], 30, 30, 18, BLUE)
        s.text(76, 22, label, 10, BLUE, "Medium")
        s.text(76, 46, title, 19, weight="Medium")
        s.text(76, 80, desc, 12, MUTED, width=585)
        s.im.save(root / f"step-{i}.png")
    s = Surface((0, 0, 1000, 620))
    s.rect((0, 0, 999, 619), "white", 12, TOKENS["border"])
    s.text(27, 24, "ruang", 21, weight="SemiBold")
    s.text(120, 30, "/ Workflows", 13, MUTED)
    s.line([(0, 76), (1000, 76)])
    s.text(32, 107, "Your workflows", 27, weight="SemiBold")
    s.text(32, 151, "Alur kerja tim, tersusun di satu tempat.", 14, MUTED)
    s.rect((803, 108, 968, 148), BLUE, 7)
    s.icon("plus", 816, 122, 15, "white")
    s.text(843, 123, "New workflow", 12, "white", "Medium")
    s.text(48, 218, "NAMA ALUR", 10, MUTED, "Medium")
    s.text(678, 218, "STATUS", 10, MUTED, "Medium")
    s.text(819, 218, "DIPERBARUI", 10, MUTED, "Medium")
    for i, (name, desc, updated) in enumerate(
        [
            ("Informasi pengiriman", "Estimasi dan panduan pengiriman", "Baru saja"),
            ("Perubahan alamat", "Verifikasi alamat tujuan pesanan", "Kemarin"),
            (
                "Permintaan invoice",
                "Bantu pelanggan mendapatkan invoice",
                "2 hari lalu",
            ),
        ]
    ):
        y = 252 + i * 93
        s.line([(32, y - 10), (968, y - 10)])
        s.rect((48, y + 10, 88, y + 50), "#edf3ff", 8)
        s.icon("flow", 59, y + 21, 18, BLUE)
        s.text(108, y + 8, name, 16, weight="Medium")
        s.text(108, y + 37, desc, 12, MUTED)
        s.rect((674, y + 15, 752, y + 43), "#edf7f0", 6)
        s.text(688, y + 24, "Aktif", 11, "#167451", "Medium")
        s.text(820, y + 24, updated, 12, MUTED)
    s.im.save(root / "workflow-list.png")
    s = Surface((0, 0, 800, 480))
    s.rect((0, 0, 799, 479), "white", 12, TOKENS["border"])
    s.text(28, 26, "Workflow baru", 24, weight="SemiBold")
    s.text(28, 69, "Atur respons sesuai kebutuhan tim.", 14, MUTED)
    for i, (label, value) in enumerate(
        [
            ("Nama alur", "Informasi pengiriman"),
            ("Pemicu", "Pertanyaan tentang pengiriman"),
            ("Sumber pengetahuan", "Panduan pengiriman · Terverifikasi"),
        ]
    ):
        y = 127 + i * 88
        s.text(30, y, label, 12, MUTED)
        s.rect((28, y + 27, 772, y + 72), "#fafbfe", 7, TOKENS["border"])
        s.text(43, y + 43, value, 15)
    s.rect((611, 419, 772, 459), BLUE, 7)
    s.text(637, 433, "Buat workflow", 13, "white", "Medium")
    s.im.save(root / "form.png")


def text(identifier, value, x=640, y=350, size=52, color=INK, **extra):
    return {
        "id": identifier,
        "type": "text",
        "text": value,
        "width": 1200,
        "height": 190,
        "x": x,
        "y": y,
        "size": size,
        "color": color,
        "weight": "Medium",
        **extra,
    }


def image(identifier, src, w, h, x=640, y=370, **extra):
    return {
        "id": identifier,
        "type": "image",
        "src": "../assets/" + src + ".png",
        "width": w,
        "height": h,
        "x": x,
        "y": y,
        **extra,
    }


def enter(node, duration, delay=0, dy=22):
    node = copy.deepcopy(node)
    node["start"] = delay
    k = node.setdefault("keyframes", {})
    k.setdefault(
        "opacity",
        [
            [delay, 0],
            [delay + 0.35, 1, "out_cubic"],
            [duration - 0.25, 1],
            [duration, 0],
        ],
    )
    k.setdefault(
        "y",
        [
            [delay, node.get("y", 360) + dy],
            [delay + 0.6, node.get("y", 360), "out_cubic"],
        ],
    )
    return node


def ui_group(
    identifier,
    duration,
    knowledge=True,
    reply=True,
    scale=0.82,
    x=640,
    y=385,
    content=None,
):
    children = []
    for part, (px, py, w, h) in PARTS.items():
        if part == "knowledge" and not knowledge or part == "reply" and not reply:
            continue
        children.append(
            {
                "id": identifier + "-" + part,
                "type": "inbox-part",
                "part": part,
                "content": {
                    "brand": "ruang",
                    "workspace": "Support workspace",
                    **(content or {}),
                },
                "width": w,
                "height": h,
                "x": px + w / 2,
                "y": py + h / 2,
            }
        )
    return {
        "id": identifier,
        "type": "group",
        "width": 1280,
        "height": 760,
        "x": x,
        "y": y,
        "scale": scale,
        "children": children,
    }


def workflow(identifier, saved=False, stagger=False):
    children = [
        image(identifier + "-frame", f"workflow-frame-{saved}", 1000, 620, 500, 310)
    ]
    for i in range(3):
        if i < 2:
            children.append(
                {
                    "id": identifier + f"-line{i}",
                    "type": "rect",
                    "width": 2,
                    "height": 24,
                    "x": 290,
                    "y": 299 + i * 134,
                    "fill": "#cddcf3",
                    "radius": 0,
                }
            )
        node = image(
            identifier + f"-step{i}", f"step-{i}", 690, 116, 610, 235 + i * 134
        )
        if stagger:
            node = enter(node, 7, 0.4 + i * 1.55, 16)
            delay = 0.4 + i * 1.55
            node["keyframes"]["opacity"] = [[delay, 0], [delay + 0.35, 1, "out_cubic"]]
        children.append(node)
    return {
        "id": identifier,
        "type": "group",
        "width": 1000,
        "height": 620,
        "x": 640,
        "y": 390,
        "children": children,
    }


def shots(out):
    specs = []
    light = {
        "base": "#edf5ff",
        "lights": [
            {"x": 0.5, "y": 0.35, "radius": 0.95, "color": "#ffffff"},
            {"x": 0.9, "y": 1, "radius": 0.4, "color": "#9bc9ff"},
        ],
    }
    blue = {
        "base": "#367eeb",
        "lights": [
            {"x": 0.3, "y": 0.1, "radius": 0.95, "color": "#d9efff"},
            {"x": 0.6, "y": 0.45, "radius": 0.65, "color": "#f4fbff"},
        ],
    }
    dark = {
        "base": "#071928",
        "lights": [
            {"x": 0.75, "y": 0.15, "radius": 0.5, "color": "#174e7c"},
            {"x": 0.05, "y": 0.95, "radius": 0.5, "color": "#123d68"},
        ],
    }
    for i, d in enumerate(DURATIONS):
        layers = []
        bg = copy.deepcopy(
            dark
            if i in (10, 12, 20)
            else blue if i in (3, 4, 5, 6, 8, 9, 11, 13, 14, 15, 16, 17, 19) else light
        )
        if i in (0, 1):
            for j, (px, py, angle) in enumerate(
                [(110, 110, -4), (1110, 150, 4), (180, 620, 2), (1140, 610, -3)]
            ):
                card = image(
                    f"repeat{i}-{j}",
                    "conversations",
                    220,
                    510,
                    px,
                    py,
                    rotation=angle,
                    opacity=0.38,
                )
                card["keyframes"] = {
                    "y": [[0, py + 20], [d, py - 12, "linear"]],
                    "opacity": [[0, 0.12], [1, 0.38], [d - 0.5, 0.38], [d, 0.18]],
                }
                layers.append(card)
            layers.append(
                enter(
                    text(
                        f"headline{i}",
                        (
                            "Pertanyaan yang sama."
                            if i == 0
                            else "Dicari lagi.\nDijawab lagi."
                        ),
                        size=55,
                    ),
                    d,
                    0.15,
                    10,
                )
            )
        elif i == 2:
            n = text("stop", "Cukup.", size=94)
            n["keyframes"] = {
                "scale": [[0, 2.5], [0.65, 1, "out_cubic"], [2.3, 1], [3, 0.9]],
                "blur": [[0, 10], [0.6, 0], [2.5, 0], [3, 4]],
                "opacity": [[0, 0], [0.15, 1], [2.65, 1], [3, 0]],
            }
            layers = [n]
        elif i == 3:
            layers = [
                enter(text("meet", "Kenalkan,", y=288, size=32), d, 0.1),
                enter(
                    text("brand-intro", "Ruang.", y=380, size=86, color=BLUE), d, 0.45
                ),
            ]
        elif i == 4:
            layers = [
                enter(
                    text(
                        "overview-title",
                        "Satu ruang untuk seluruh percakapan.",
                        y=76,
                        size=30,
                    ),
                    d,
                    0.15,
                    10,
                )
            ]
            n = ui_group("overview", d, False, False, scale=0.78, y=430)
            n["keyframes"] = {
                "y": [[0, 950], [1.15, 425, "out_cubic"], [d, 402]],
                "tilt_y": [[0, -18], [2, -8], [d, 0]],
                "tilt_x": [[0, 14], [d, 0]],
                "scale": [[0, 0.7], [2, 0.78], [d, 0.82]],
            }
            layers.append(n)
        elif i == 5:
            n = ui_group("inspect", d, False, False)
            n["keyframes"] = {
                "scale": [[0, 0.82], [1.5, 1.25], [d, 1.32]],
                "x": [[0, 640], [1.5, 350], [d, 340]],
                "y": [[0, 402], [1.5, 440], [d, 425]],
            }
            layers = [n]
        elif i == 6:
            n = ui_group("search-context", d, False, False, scale=0.65, x=310, y=410)
            n["keyframes"] = {
                "x": [[0, 340], [0.8, 275]],
                "scale": [[0, 1.32], [0.8, 0.65]],
                "y": [[0, 425], [0.8, 410]],
            }
            layers = [
                n,
                enter(
                    image("verified-source", "source", 620, 430, x=920, y=395),
                    d,
                    1.3,
                    14,
                ),
                enter(
                    text("search-label", "Temukan sumbernya.", x=875, y=99, size=32),
                    d,
                    0.6,
                    8,
                ),
            ]
        elif i == 7:
            layers = [
                enter(
                    text("approved", "Jawaban ditemukan.", y=294, size=52), d, 0.1, 10
                ),
                enter(
                    text(
                        "approve-learning",
                        "Simpan sebagai pengetahuan.",
                        y=391,
                        size=36,
                        color=BLUE,
                    ),
                    d,
                    1.05,
                    12,
                ),
            ]
        elif i == 8:
            layers = [
                {
                    "id": "learning",
                    "type": "progress",
                    "width": 900,
                    "height": 88,
                    "x": 640,
                    "y": 360,
                    "label": "Memahami konteks...",
                    "keyframes": {
                        "progress": [[0, 0], [3.6, 1, "linear"]],
                        "scale": [
                            [0, 1.35],
                            [0.6, 1, "out_cubic"],
                            [3.5, 1],
                            [5, 0.72],
                        ],
                        "y": [[0, 360], [3.5, 360], [5, 185]],
                        "opacity": [[0, 0], [0.25, 1]],
                    },
                }
            ]
        elif i == 9:
            layers = [
                {
                    "id": "learned-bar",
                    "type": "progress",
                    "width": 900,
                    "height": 88,
                    "x": 640,
                    "y": 185,
                    "scale": 0.72,
                    "label": "Pengetahuan siap digunakan",
                    "progress": 1,
                    "keyframes": {"opacity": [[0, 1], [1, 1], [1.5, 0]]},
                },
                enter(
                    image("knowledge-created", "knowledge-card", 720, 400, y=410),
                    d,
                    0.35,
                    25,
                ),
            ]
        elif i == 10:
            layers = [
                enter(
                    text("reusable", "Satu jawaban.", y=290, size=48, color="white"),
                    d,
                    0.1,
                    10,
                ),
                enter(
                    text(
                        "shared",
                        "Pengetahuan bersama.",
                        y=388,
                        size=56,
                        color="#64b9ff",
                    ),
                    d,
                    0.65,
                    12,
                ),
            ]
        elif i == 11:
            n = ui_group(
                "next-question",
                d,
                True,
                False,
                0.79,
                y=423,
                content={
                    "customer": "Bima Prasetyo",
                    "initials": "BP",
                    "message": "Halo, berapa lama estimasi pengiriman regulernya?",
                    "acknowledgement": "Saya temukan panduan yang sesuai untuk pertanyaan Anda.",
                },
            )
            x, y, w, h = PARTS["reply"]
            n["children"].append(
                enter(
                    {
                        "id": "next-reply",
                        "type": "inbox-part",
                        "part": "reply",
                        "width": w,
                        "height": h,
                        "x": x + w / 2,
                        "y": y + h / 2,
                        "content": {
                            "reply": "Pengiriman reguler biasanya tiba 2–3 hari kerja setelah paket dikirim. Nomor resi akan kami kirimkan melalui email.",
                            "sent": True,
                        },
                    },
                    d,
                    2.2,
                    8,
                )
            )
            n["keyframes"] = {
                "scale": [[0, 0.79], [d, 0.84]],
                "y": [[0, 423], [d, 422]],
            }
            layers = [
                n,
                enter(
                    text(
                        "next-title",
                        "Pertanyaan berikutnya? Jawaban sudah siap.",
                        y=75,
                        size=29,
                    ),
                    d,
                    0.1,
                    8,
                ),
            ]
        elif i == 12:
            layers = [
                enter(
                    text(
                        "your-rules",
                        "Anda tentukan alurnya.",
                        y=285,
                        size=51,
                        color="white",
                    ),
                    d,
                    0.1,
                    10,
                ),
                enter(
                    text(
                        "system-runs",
                        "Ruang menjalankannya.",
                        y=388,
                        size=48,
                        color="#64b9ff",
                    ),
                    d,
                    0.8,
                    10,
                ),
            ]
        elif i == 13:
            n = {
                "id": "menu",
                "type": "menu",
                "width": 280,
                "height": 255,
                "title": "Support workspace",
                "items": ["Inbox", "Knowledge", "Workflows", "Reports"],
                "selected": 2,
                "x": 350,
                "y": 355,
                "shadow": True,
                "progress": 1,
            }
            layers = [
                enter(n, d, 0.1, 12),
                enter(
                    text("configure-once", "Atur satu kali.", x=860, y=350, size=51),
                    d,
                    0.3,
                    8,
                ),
            ]
            layers.append(
                {
                    "id": "menu-pointer",
                    "type": "cursor",
                    "width": 28,
                    "height": 38,
                    "x": 535,
                    "y": 540,
                    "start": 1,
                    "keyframes": {
                        "x": [[1, 535], [1.8, 314]],
                        "y": [[1, 540], [1.8, 380]],
                        "scale": [[1, 1], [2.1, 1], [2.22, 0.97], [2.35, 1]],
                    },
                }
            )
        elif i == 14:
            n = image("configure-form", "form", 800, 480, y=383)
            n["keyframes"] = {
                "tilt_y": [[0, -15], [1, 0]],
                "scale": [[0, 0.9], [1, 1], [d, 1.13]],
                "y": [[0, 800], [1, 385], [d, 375]],
            }
            layers = [n]
        elif i == 15:
            n = workflow("build", stagger=True)
            n["keyframes"] = {
                "scale": [[0, 0.92], [d, 0.98]],
                "y": [[0, 395], [d, 390]],
            }
            layers = [n]
        elif i == 16:
            n = workflow("save-before")
            n["end"] = 1.8
            n["keyframes"] = {
                "scale": [[0, 0.98], [1, 1.22]],
                "x": [[0, 640], [1, 375]],
                "y": [[0, 390], [1, 550]],
            }
            a = workflow("save-after", saved=True)
            a["start"] = 1.65
            a["scale"] = 1.22
            a["x"] = 375
            a["y"] = 550
            a["keyframes"] = {"opacity": [[1.65, 0], [1.85, 1]]}
            pointer = {
                "id": "save-pointer",
                "type": "cursor",
                "width": 28,
                "height": 38,
                "x": 1000,
                "y": 450,
                "keyframes": {
                    "x": [[0, 1000], [1.35, 876]],
                    "y": [[0, 450], [1.35, 234]],
                    "scale": [[0, 1], [1.6, 1], [1.7, 0.97], [1.85, 1]],
                },
            }
            layers = [n, a, pointer]
        elif i == 17:
            n = image("workflow-list", "workflow-list", 1000, 620, y=390)
            n["keyframes"] = {
                "scale": [[0, 1.08], [d, 0.95]],
                "tilt_y": [[0, 5], [d, 0]],
            }
            layers = [n]
        elif i == 18:
            layers = [
                enter(
                    text("less-repeat", "Lebih sedikit mengulang.", y=290, size=49),
                    d,
                    0.1,
                    8,
                ),
                enter(
                    text(
                        "more-done",
                        "Lebih banyak menyelesaikan.",
                        y=388,
                        size=43,
                        color=BLUE,
                    ),
                    d,
                    0.85,
                    12,
                ),
            ]
        elif i == 19:
            layers = [
                enter(text("ruang-brand", "ruang", size=98, color=BLUE), d, 0.1, 8)
            ]
        elif i == 20:
            layers = [
                enter(
                    text(
                        "closing",
                        "Ruang untuk pekerjaan\nyang penting.",
                        size=49,
                        color="white",
                    ),
                    d,
                    0.05,
                    10,
                ),
                text(
                    "concept-note",
                    "Konsep produk fiktif · Motion dibuat dengan Gilvy",
                    y=635,
                    size=15,
                    color="#a5b6c7",
                ),
            ]
        specs.append(
            {
                "style": "product",
                "size": [1280, 720],
                "fps": 30,
                "duration": d,
                "samples": 1,
                "shutter": 0.5,
                "audio": None,
                "background": bg,
                "layers": layers,
            }
        )
    for i, spec in enumerate(specs):
        path = out / "shots" / f"{i:02}.yaml"
        path.parent.mkdir(exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
    (out / "timeline.json").write_text(
        json.dumps(
            [
                {"id": i, "name": name, "start": sum(DURATIONS[:i]), "duration": d}
                for i, (name, d) in enumerate(zip(NAMES, DURATIONS))
            ],
            indent=2,
        )
    )
    return specs


def music(path):
    sr = 24000
    total = sum(DURATIONS)
    t = np.arange(sr * total) / sr
    audio = np.zeros(len(t))
    beat = 60 / 90
    chords = [
        (146.83, 220, 293.66, 369.99),
        (130.81, 196, 261.63, 329.63),
        (164.81, 246.94, 329.63, 392),
        (110, 164.81, 220, 277.18),
    ]
    for k, a in enumerate(np.arange(0, total, 8 * beat)):
        n = int(a * sr)
        length = min(len(t) - n, int((8 * beat + 0.8) * sr))
        local = np.arange(length) / sr
        env = np.minimum(1, local / 0.4) * np.minimum(
            1, np.maximum(0, (8 * beat + 0.8 - local) / 0.8)
        )
        for f in chords[k % 4]:
            audio[n : n + length] += 0.022 * np.sin(2 * np.pi * f * local) * env
    for k, a in enumerate(np.arange(0, total, beat)):
        n = int(a * sr)
        length = min(len(t) - n, int(0.24 * sr))
        local = np.arange(length) / sr
        audio[n : n + length] += (
            0.035
            * np.sin(2 * np.pi * (52 * local + 18 * (1 - np.exp(-local * 18)) / 18))
            * np.exp(-local * 24)
        )
        if k % 2:
            length = min(len(t) - n, int(0.6 * sr))
            local = np.arange(length) / sr
            f = chords[(k // 8) % 4][k % 4] * 2
            audio[n : n + length] += (
                0.016 * np.sin(2 * np.pi * f * local) * np.exp(-local * 7)
            )
    audio *= np.minimum(1, t / 1.5) * np.minimum(1, (total - t) / 2)
    stereo = np.stack([audio, audio * 0.97], 1)
    stereo = np.clip(stereo, -0.9, 0.9)
    with wave.open(str(path), "w") as f:
        f.setparams((2, 2, sr, 0, "NONE", "not compressed"))
        f.writeframes((stereo * 32767).astype("<i2").tobytes())


def render_one(args):
    spec, output = args
    return render_product(spec, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    assets(out / "assets")
    specs = shots(out)
    sheet = Image.new("RGB", (1280, 204 * math.ceil(len(specs) / 4)), "#1c2738")
    pen = ImageDraw.Draw(sheet)
    for i, spec in enumerate(specs):
        film = load_product(out / "shots" / f"{i:02}.yaml")
        im = film.frame(spec["duration"] * 0.6).resize(
            (320, 180), Image.Resampling.LANCZOS
        )
        x, y = i % 4 * 320, i // 4 * 204
        sheet.paste(im, (x, y + 24))
        pen.text((x + 6, y + 6), f"{sum(DURATIONS[:i]):02}s  {NAMES[i]}", fill="white")
    sheet.save(out / "storyboard.jpg", quality=94)
    print("Storyboard ready", out / "storyboard.jpg", flush=True)
    if not args.render:
        return
    jobs = [
        (str(out / "shots" / f"{i:02}.yaml"), str(out / f"shot-{i:02}.mp4"))
        for i in range(len(specs))
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(render_one, job): i for i, job in enumerate(jobs)}
        for future in as_completed(futures):
            i = futures[future]
            future.result()
            print(f"Shot {i+1}/{len(specs)} complete", flush=True)
    listing = out / "concat.txt"
    listing.write_text("".join(f"file 'shot-{i:02}.mp4'\n" for i in range(len(specs))))
    music(out / "ambient.wav")
    target = out / "Ruang_Product_Film_95s.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-i",
            str(out / "ambient.wav"),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-af",
            "loudnorm=I=-22:TP=-2:LRA=8",
            "-t",
            str(sum(DURATIONS)),
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
    )
    print(target, flush=True)


if __name__ == "__main__":
    main()
