"""Shared product UI tokens and independently drawable inbox surfaces.

All demo identities/content are fictional. Layout coordinates are native 1280x760.
"""

from __future__ import annotations

from functools import lru_cache
import json

from PIL import Image, ImageDraw, ImageFont

from gilvy.theme import bundled_fonts

TOKENS = {
    "ink": "#202631",
    "secondary": "#555e6d",
    "muted": "#667181",
    "border": "#e5e8ee",
    "surface": "#ffffff",
    "sidebar": "#f8f9fb",
    "blue": "#2864e9",
    "selection": "#eef4ff",
    "green": "#167451",
    "space": (4, 8, 12, 16, 24, 32),
    "radius": (6, 8, 12),
    "type": {"micro": 11, "label": 12, "body": 14, "title": 16, "heading": 22},
}
PARTS = {
    "shell": (0, 0, 1280, 760),
    "sidebar": (0, 0, 180, 760),
    "conversations": (180, 64, 300, 696),
    "thread": (480, 64, 520, 696),
    "customer": (1000, 64, 280, 256),
    "knowledge": (1000, 320, 280, 440),
    "reply": (504, 518, 472, 214),
}
DEFAULT_CONTENT = {
    "brand": "gilvy",
    "workspace": "Studio workspace",
    "agent": "Alya Rahma",
    "customer": "Nadia Putri",
    "company": "Aruna Studio",
    "initials": "NP",
    "email": "nadia@example.test",
    "subject": "Estimasi pengiriman pesanan",
    "message": "Halo, saya mau tanya. Pesanan saya sudah diproses sejak kemarin. Kira-kira kapan paketnya sampai?",
    "acknowledgement": "Halo Nadia, terima kasih sudah menghubungi kami. Saya bantu cek informasinya, ya.",
    "source_title": "Pengiriman reguler",
    "source_path": "Pusat bantuan / Pengiriman",
    "source_text": "Pesanan dikirim dalam 1 hari kerja setelah pembayaran. Estimasi tiba 2–3 hari kerja, bergantung pada tujuan.",
    "reply": "Halo Nadia, pesanan Anda sedang disiapkan. Estimasi pengiriman reguler 2–3 hari kerja setelah paket dikirim. Kami akan mengirim nomor resinya melalui email.",
    "sent": False,
}


@lru_cache(maxsize=128)
def _font(size, weight="Regular"):
    return ImageFont.truetype(str(bundled_fonts() / f"Poppins-{weight}.ttf"), size * 2)


def fit_text(value, width, size=14, weight="Regular"):
    """Ellipsize by measured glyph width, not character count."""
    f = _font(size, weight)
    if f.getlength(value) <= width * 2:
        return value
    while value and f.getlength(value + "…") > width * 2:
        value = value[:-1]
    return value + "…" if value else ""


def wrap_text(value, width, size=14, weight="Regular"):
    lines = []
    line = ""
    f = _font(size, weight)
    for word in value.split():
        candidate = (line + " " + word).strip()
        if f.getlength(candidate) > width * 2 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


class Surface:
    def __init__(self, rect):
        self.x, self.y, w, h = rect
        self.im = Image.new("RGBA", (w * 2, h * 2))
        self.d = ImageDraw.Draw(self.im)

    def box(self, b):
        return (
            (b[0] - self.x) * 2,
            (b[1] - self.y) * 2,
            (b[2] - self.x) * 2,
            (b[3] - self.y) * 2,
        )

    def rect(self, b, fill="white", radius=0, border=None):
        self.d.rounded_rectangle(
            self.box(b), radius=radius * 2, fill=fill, outline=border, width=2
        )

    def line(self, pts, fill=None, width=1):
        self.d.line(
            [((x - self.x) * 2, (y - self.y) * 2) for x, y in pts],
            fill=fill or TOKENS["border"],
            width=max(1, round(width * 2)),
            joint="curve",
        )

    def text(self, x, y, value, size=14, fill=None, weight="Regular", width=None):
        if width is not None:
            value = fit_text(value, width, size, weight)
        self.d.text(
            ((x - self.x) * 2, (y - self.y) * 2),
            value,
            font=_font(size, weight),
            fill=fill or TOKENS["ink"],
            anchor="lt",
        )

    def paragraph(
        self, x, y, value, width, size=14, fill=None, max_lines=8, line_height=23
    ):
        lines = wrap_text(value, width, size)
        for i, line in enumerate(lines[:max_lines]):
            if i == max_lines - 1 and len(lines) > max_lines:
                line = fit_text(line + " …", width, size)
            self.text(x, y + i * line_height, line, size, fill, width=width)
        return min(len(lines), max_lines) * line_height

    def avatar(self, x, y, initials, fill="#eee7dc", size=32):
        self.d.ellipse(self.box((x, y, x + size, y + size)), fill=fill)
        f = _font(11, "Medium")
        length = f.getlength(initials) / 2
        self.text(
            x + (size - length) / 2,
            y + (size - 11) / 2,
            initials,
            11,
            "#635343",
            "Medium",
        )

    def icon(self, name, x, y, size=16, fill=None):
        col = fill or TOKENS["secondary"]
        # Normalized 16px line icons, consistently stroked at 1.5px.
        shapes = {
            "inbox": [
                [(2, 3), (14, 3), (14, 13), (2, 13), (2, 3)],
                [(2, 9), (6, 9), (7, 11), (9, 11), (10, 9), (14, 9)],
            ],
            "book": [
                [(3, 2), (13, 2), (13, 14), (3, 14), (3, 2)],
                [(6, 2), (6, 14)],
                [(8, 6), (11, 6)],
                [(8, 9), (11, 9)],
            ],
            "flow": [
                [(3, 2), (7, 2), (7, 6), (3, 6), (3, 2)],
                [(10, 10), (14, 10), (14, 14), (10, 14), (10, 10)],
                [(5, 6), (5, 12), (10, 12)],
            ],
            "chart": [
                [(2, 13), (14, 13)],
                [(4, 10), (4, 7)],
                [(8, 10), (8, 4)],
                [(12, 10), (12, 1)],
            ],
            "check": [[(3, 8), (6, 11), (13, 4)]],
            "plus": [[(3, 8), (13, 8)], [(8, 3), (8, 13)]],
            "chevron": [[(5, 6), (8, 9), (11, 6)]],
            "send": [[(2, 3), (14, 8), (2, 13), (5, 8), (2, 3)], [(5, 8), (14, 8)]],
            "arrow": [[(3, 8), (13, 8)], [(9, 4), (13, 8), (9, 12)]],
            "filter": [[(2, 4), (14, 4)], [(4, 8), (12, 8)], [(6, 12), (10, 12)]],
            "user": [[(3, 14), (3, 12), (5, 10), (11, 10), (13, 12), (13, 14)]],
            "settings": [
                [(8, 1), (8, 4)],
                [(8, 12), (8, 15)],
                [(1, 8), (4, 8)],
                [(12, 8), (15, 8)],
            ],
        }
        for points in shapes.get(name, []):
            self.line(
                [(x + a * size / 16, y + b * size / 16) for a, b in points], col, 1.5
            )
        if name in ("search", "user", "settings"):
            b = {
                "search": (2, 2, 10, 10),
                "user": (5, 1, 11, 7),
                "settings": (4, 4, 12, 12),
            }[name]
            self.d.ellipse(
                self.box(
                    (
                        x + b[0] * size / 16,
                        y + b[1] * size / 16,
                        x + b[2] * size / 16,
                        y + b[3] * size / 16,
                    )
                ),
                outline=col,
                width=3,
            )
            if name == "search":
                self.line(
                    [
                        (x + 10 * size / 16, y + 10 * size / 16),
                        (x + 14 * size / 16, y + 14 * size / 16),
                    ],
                    col,
                    1.5,
                )


def _paint(part, s, c, p):
    ink, muted, border, blue = (
        TOKENS["ink"],
        TOKENS["muted"],
        TOKENS["border"],
        TOKENS["blue"],
    )
    if part == "shell":
        s.rect((0, 0, 1279, 759), radius=12, border=border)
        s.line([(180, 64), (1280, 64)])
        s.text(204, 24, "Inbox", 18, weight="SemiBold")
        s.text(274, 27, "/", 13, muted)
        s.text(294, 27, "All conversations", 13, TOKENS["secondary"])
        s.rect((1136, 17, 1256, 47), "#fafbfc", 6, border)
        s.icon("user", 1148, 24, 14)
        s.text(1170, 25, "Alya", 12)
        s.icon("chevron", 1231, 25, 13)
        s.line([(180, 0), (180, 760)])
    elif part == "sidebar":
        s.rect((0, 0, 179, 759), TOKENS["sidebar"], 12)
        s.rect((16, 18, 43, 45), "#252c38", 7)
        s.line([(25, 25), (25, 38), (34, 38), (34, 31), (30, 31)], "white", 2)
        s.text(53, 23, c["brand"], 20, weight="SemiBold", width=112)
        s.rect((12, 76, 168, 120), "#ffffff", 7, border)
        s.text(23, 87, c["workspace"], 11, weight="Medium", width=126)
        s.icon("chevron", 145, 91, 11)
        for i, (icon, label) in enumerate(
            (
                ("inbox", "Inbox"),
                ("book", "Knowledge"),
                ("flow", "Workflows"),
                ("chart", "Reports"),
            )
        ):
            y = 150 + i * 44
            if i == 0:
                s.rect((12, y - 9, 168, y + 28), "#eaf0fc", 7)
            s.icon(icon, 24, y, 17, blue if i == 0 else muted)
            s.text(
                52,
                y + 1,
                label,
                13,
                blue if i == 0 else TOKENS["secondary"],
                "Medium" if i == 0 else "Regular",
            )
            if i == 0:
                s.text(142, y + 2, "12", 11, blue, "Medium")
        s.text(24, 364, "TEAM", 10, muted, "Medium")
        for i, label in enumerate(("Assigned to me", "Unassigned", "Resolved")):
            s.text(30, 398 + i * 35, label, 12, TOKENS["secondary"])
        s.line([(16, 654), (164, 654)])
        s.icon("settings", 24, 675)
        s.text(52, 676, "Settings", 12, TOKENS["secondary"])
        s.avatar(22, 714, "AR", "#dbe8e2", 28)
        s.text(59, 717, c["agent"], 11, "#4f5a65", "Medium", width=108)
        s.line([(179, 0), (179, 760)])
    elif part == "conversations":
        s.rect((180, 64, 479, 759))
        s.text(204, 87, "All conversations", 17, weight="SemiBold")
        s.rect((419, 83, 454, 108), "#f1f3f6", 6)
        s.text(428, 90, "12", 11, TOKENS["secondary"], "Medium")
        s.rect((200, 123, 460, 158), "#fafbfc", 7, border)
        s.icon("search", 212, 133, 14, muted)
        s.text(235, 135, "Search conversations", 11, muted)
        s.text(204, 180, "Open", 12, ink, "Medium")
        s.text(260, 180, "Resolved", 12, muted)
        s.line([(204, 205), (242, 205)], blue, 2)
        s.icon("filter", 437, 178, 16, muted)
        s.line([(180, 209), (480, 209)])
        entries = [
            (
                c["customer"],
                c["subject"],
                "Halo, saya mau tanya...",
                "NP",
                "2m",
                "Delivery",
            ),
            (
                "Bima Prasetyo",
                "Akses akun baru",
                "Sudah bisa login, terima kasih!",
                "BP",
                "8m",
                "Account",
            ),
            (
                "Dewi Lestari",
                "Perubahan alamat",
                "Bisa dibantu ubah alamatnya?",
                "DL",
                "15m",
                "Delivery",
            ),
            (
                "Raka Saputra",
                "Invoice pembayaran",
                "Mohon kirim ulang invoice...",
                "RS",
                "28m",
                "Billing",
            ),
            (
                "Maya Anggraini",
                "Informasi produk",
                "Ada pilihan warna lainnya?",
                "MA",
                "42m",
                "Product",
            ),
        ]
        for i, (name, subject, preview, initial, time, tag) in enumerate(entries):
            y = 210 + i * 104
            if i == 0:
                s.rect((180, y, 479, y + 104), TOKENS["selection"])
            s.avatar(
                201,
                y + 18,
                initial,
                ["#efe4d5", "#e3e9f6", "#e5eee5", "#eee5f0", "#f4e3e1"][i],
            )
            s.text(245, y + 18, name, 12, weight="SemiBold", width=160)
            s.text(432, y + 20, time, 10, muted)
            s.text(245, y + 41, subject, 11, TOKENS["secondary"], width=208)
            s.text(245, y + 61, preview, 10, muted, width=208)
            s.rect(
                (245, y + 80, 309 if tag == "Delivery" else 305, y + 97),
                "#e6ecf5" if i == 0 else "#f2f4f7",
                4,
            )
            s.text(252, y + 84, tag, 9, "#65738a")
            s.line([(200, y + 104), (460, y + 104)])
        s.line([(479, 64), (479, 760)])
    elif part == "thread":
        s.rect((480, 64, 999, 759))
        s.avatar(504, 83, c["initials"], size=36)
        s.text(552, 85, c["customer"], 15, weight="SemiBold", width=260)
        s.text(552, 109, "Email · Conversation #1042", 10, muted)
        s.rect((873, 87, 974, 115), "#f7f9fc", 6, border)
        s.text(888, 95, "Open", 11, TOKENS["secondary"])
        s.icon("chevron", 951, 95, 12)
        s.line([(480, 139), (1000, 139)])
        s.text(504, 160, c["subject"], 17, weight="SemiBold", width=472)
        s.text(714, 203, "TODAY", 9, muted, "Medium")
        s.avatar(504, 239, c["initials"], size=28)
        s.text(544, 239, c["customer"], 11, weight="Medium")
        s.text(874, 240, "09:41", 10, muted)
        s.rect((544, 263, 951, 374), "#f5f6f8", 10)
        s.paragraph(560, 278, c["message"], 373, 14, max_lines=4, line_height=23)
        s.text(544, 400, c["agent"], 11, weight="Medium")
        s.text(874, 401, "09:42", 10, muted)
        s.paragraph(
            544,
            425,
            c["acknowledgement"],
            407,
            14,
            TOKENS["secondary"],
            max_lines=3,
            line_height=23,
        )
        s.line([(1000, 64), (1000, 760)])
    elif part in ("knowledge", "customer"):
        s.rect((1000, 64, 1279, 759), "#fbfcfe")
        s.text(1024, 90, "Customer details", 13, weight="SemiBold")
        s.avatar(1024, 125, c["initials"], size=36)
        s.text(1072, 129, c["customer"], 12, weight="Medium", width=180)
        s.text(1072, 151, c["company"], 10, muted, width=180)
        s.text(1024, 189, "Email", 10, muted)
        s.text(1024, 210, c["email"], 11, TOKENS["secondary"], width=230)
        s.text(1024, 246, "Tags", 10, muted)
        s.rect((1024, 269, 1097, 292), "#f0f3f8", 5)
        s.text(1033, 276, "Customer", 10, "#69758b")
        s.line([(1024, 319), (1256, 319)])
        s.icon("book", 1024, 343, 16, blue)
        s.text(1049, 344, "Knowledge", 13, weight="SemiBold")
        s.rect((1024, 382, 1256, 597), "#ffffff", 9, border)
        s.rect((1040, 398, 1159, 421), "#ecf6f0", 5)
        s.icon("check", 1047, 404, 12, TOKENS["green"])
        s.text(1065, 406, "Verified source", 9, TOKENS["green"], "Medium")
        s.text(1040, 440, c["source_title"], 13, weight="Medium", width=199)
        s.paragraph(
            1040,
            470,
            c["source_text"],
            199,
            12,
            TOKENS["secondary"],
            max_lines=5,
            line_height=19,
        )
        s.text(1040, 574, "View source", 10, blue, "Medium")
        s.icon("arrow", 1217, 572, 13, blue)
        s.text(1024, 620, c["source_path"], 9, muted, width=231)
        s.line([(1000, 64), (1000, 760)])
    elif part == "reply":
        s.rect((504, 518, 976, 732), "#ffffff", 10, "#cbdaf8")
        s.rect((505, 519, 975, 556), "#f7faff", 10)
        s.icon("book", 520, 532, 13, blue)
        s.text(542, 532, "Suggested reply", 11, blue, "Medium")
        s.text(839, 534, "Based on 1 source", 9, muted)
        visible = c["reply"][: int(len(c["reply"]) * p + 1e-8)]
        s.paragraph(
            520, 574, visible, 439, 13, TOKENS["secondary"], max_lines=4, line_height=22
        )
        s.line([(520, 680), (960, 680)])
        s.text(520, 704, "Aa", 12, muted, "Medium")
        s.text(550, 705, "+", 15, muted)
        if c["sent"]:
            s.rect((850, 694, 960, 720), "#edf6f0", 6)
            s.icon("check", 861, 702, 12, TOKENS["green"])
            s.text(880, 702, "Reply sent", 10, TOKENS["green"], "Medium")
        else:
            s.rect((850, 694, 960, 720), blue, 6)
            s.icon("send", 862, 701, 13, "white")
            s.text(885, 702, "Send reply", 10, "white", "Medium")


def inbox_part(part, content=None, progress=1.0):
    """Return one surface at native resolution; text/symbols supersample at 2x."""
    return _part_cached(
        part, json.dumps(content or {}, sort_keys=True), round(progress, 4)
    ).copy()


@lru_cache(maxsize=24)
def _part_cached(part, serialized, progress):
    c = {**DEFAULT_CONTENT, **json.loads(serialized)}
    s = Surface(PARTS[part])
    _paint(part, s, c, progress)
    return s.im.resize((PARTS[part][2], PARTS[part][3]), Image.Resampling.LANCZOS)


def inbox(content=None, progress=1.0):
    im = Image.new("RGBA", (1280, 760))
    for part, (x, y, _, _) in PARTS.items():
        im.alpha_composite(inbox_part(part, content, progress), (x, y))
    return im
