"""Genera el vídeo promocional vertical (1080x1920) de Servicios Planet.

Uso: python3 make_video.py <carpeta_imagenes> <salida.mp4>
"""
import math
import os
import random
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
ASSETS = sys.argv[1] if len(sys.argv) > 1 else "assets"
OUT = sys.argv[2] if len(sys.argv) > 2 else "servicios_planet_promo.mp4"
FRAMES_DIR = os.environ.get("FRAMES_DIR", "frames")

FONT_DIR = "/usr/share/fonts/opentype/inter/"
PINK = (236, 72, 153)
VIOLET = (139, 92, 246)
BLUE = (99, 102, 241)
WHITE = (255, 255, 255)
SOFT = (200, 196, 230)
GREEN = (74, 222, 128)


def font(weight, size):
    return ImageFont.truetype(FONT_DIR + f"InterDisplay-{weight}.otf", size)


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def ease_back(x):
    x = clamp(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def prog(t, start, dur):
    return clamp((t - start) / dur)


def lerp(a, b, x):
    return a + (b - a) * x


# ---------- assets ----------
def load(name):
    return Image.open(os.path.join(ASSETS, name))


LOGO = load("logo.png").convert("RGBA")
GOOGLE = load("google.png").convert("RGB")
CERRAJERO = load("cerrajero.jpg").convert("RGB")
PLANET_MOBILE = load("planet_mobile.jpg").convert("RGB")
DESK = load("escritorio.jpg").convert("RGB")


def make_background():
    bg = Image.new("RGB", (W, H), (10, 6, 28))
    # degradado vertical
    top, bottom = (12, 6, 32), (34, 12, 70)
    px = bg.load()
    for y in range(H):
        c = tuple(int(lerp(top[i], bottom[i], y / H)) for i in range(3))
        for x in range(W):
            px[x, y] = c
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((-300, -200, 700, 800), fill=(120, 30, 110))
    d.ellipse((450, 1100, 1450, 2200), fill=(60, 40, 170))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    return Image.blend(bg, Image.eval(glow, lambda v: v), 0.55)


BG = make_background()
random.seed(7)
STARS = [(random.uniform(0, W), random.uniform(0, H), random.uniform(1, 3.2),
          random.uniform(0, math.tau), random.uniform(0.6, 2.0)) for _ in range(140)]


def background(t):
    img = BG.copy()
    d = ImageDraw.Draw(img)
    for x, y, r, ph, sp in STARS:
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(ph + t * sp * 2))
        yy = (y - t * 12 * r) % H
        c = int(255 * a)
        d.ellipse((x - r, yy - r, x + r, yy + r), fill=(c, c, min(255, c + 20)))
    return img


# ---------- texto ----------
def gradient(w, h, c1=PINK, c2=VIOLET):
    g = Image.new("RGB", (w, 1))
    for x in range(w):
        f = x / max(1, w - 1)
        g.putpixel((x, 0), tuple(int(lerp(c1[i], c2[i], f)) for i in range(3)))
    return g.resize((w, h))


@lru_cache(maxsize=256)
def text_layer(text, weight, size, color=WHITE, grad=False, spacing=0):
    f = font(weight, size)
    if spacing:
        widths = [f.getlength(ch) + spacing for ch in text]
        tw = int(sum(widths))
    else:
        tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    th = asc + desc
    mask = Image.new("L", (tw + 8, th + 8), 0)
    d = ImageDraw.Draw(mask)
    if spacing:
        x = 4
        for ch, wd in zip(text, widths):
            d.text((x, 4), ch, font=f, fill=255)
            x += wd
    else:
        d.text((4, 4), text, font=f, fill=255)
    if grad:
        fill = gradient(mask.width, mask.height).convert("RGBA")
    else:
        fill = Image.new("RGBA", mask.size, color + (255,))
    fill.putalpha(mask)
    # sombra suave para legibilidad
    shadow = Image.new("RGBA", (mask.width + 40, mask.height + 40), (0, 0, 0, 0))
    sm = Image.new("L", shadow.size, 0)
    sm.paste(mask, (20, 24))
    sm = sm.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.55))
    shadow.putalpha(sm)
    shadow.alpha_composite(fill, (20, 20))
    return shadow


def with_alpha(layer, a):
    if a >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return out


def put_text(img, text, weight, size, cy, t0, t, color=WHITE, grad=False,
             spacing=0, cx=W // 2, rise=60, dur=0.5, alpha=1.0):
    p = ease_out(prog(t, t0, dur))
    if p <= 0 or alpha <= 0:
        return
    layer = text_layer(text, weight, size, color, grad, spacing)
    layer = with_alpha(layer, p * alpha)
    x = int(cx - layer.width / 2)
    y = int(cy - layer.height / 2 + (1 - p) * rise)
    img.alpha_composite(layer, (x, y))


# ---------- tarjetas ----------
@lru_cache(maxsize=32)
def round_mask(w, h, r):
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), r * 2, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=32)
def card_shadow(w, h, r, glow=False):
    pad = 80
    s = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    m = Image.new("L", s.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((pad, pad + 20, pad + w, pad + h + 20), r, fill=200)
    m = m.filter(ImageFilter.GaussianBlur(35))
    col = (150, 60, 220, 255) if glow else (0, 0, 0, 255)
    s = Image.new("RGBA", s.size, col)
    s.putalpha(m)
    return s


def paste_card(img, content, cx, cy, scale=1.0, alpha=1.0, r=48, glow=True):
    if scale != 1.0:
        content = content.resize((max(1, int(content.width * scale)),
                                  max(1, int(content.height * scale))), Image.BILINEAR)
    w, h = content.size
    rr = max(4, int(r * scale))
    sh = card_shadow(w, h, rr, glow)
    img.alpha_composite(with_alpha(sh, alpha), (int(cx - sh.width / 2), int(cy - sh.height / 2)))
    c = content.convert("RGBA")
    m = round_mask(w, h, rr)
    if alpha < 1:
        m = m.point(lambda v: int(v * alpha))
    c.putalpha(m)
    img.alpha_composite(c, (int(cx - w / 2), int(cy - h / 2)))
    # borde degradado fino
    border = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((0, 0, w - 1, h - 1), rr,
                                             outline=(200, 150, 255, int(140 * alpha)), width=3)
    img.alpha_composite(border, (int(cx - w / 2), int(cy - h / 2)))


def crop_view(src, x0, y0, cw, ch, out_w, out_h):
    return src.resize((out_w, out_h), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def pill(img, cx, cy, w, h, text, size, alpha=1.0, scale=1.0, grad=True, color=None):
    w2, h2 = int(w * scale), int(h * scale)
    if w2 < 4 or h2 < 4:
        return
    fill = gradient(w2, h2).convert("RGBA") if grad else Image.new("RGBA", (w2, h2), color + (255,))
    fill.putalpha(round_mask(w2, h2, h2 // 2).point(lambda v: int(v * alpha)))
    gl = card_shadow(w2, h2, h2 // 2, True)
    img.alpha_composite(with_alpha(gl, alpha), (int(cx - gl.width / 2), int(cy - gl.height / 2)))
    img.alpha_composite(fill, (int(cx - w2 / 2), int(cy - h2 / 2)))
    lay = with_alpha(text_layer(text, "ExtraBold", max(8, int(size * scale))), alpha)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2) - 4))


def footer(img, t, alpha=1.0):
    lay = with_alpha(text_layer("serviciosplanet.es", "Bold", 40, SOFT), 0.85 * alpha)
    small = LOGO_SMALL
    total = small.width + 16 + lay.width - 40
    x = (W - total) // 2
    img.alpha_composite(with_alpha(small, alpha), (x, 1800 - small.height // 2))
    img.alpha_composite(lay, (x + small.width + 16 - 20, 1800 - lay.height // 2))




def logo_with_disc(size):
    # disco claro dentro del anillo para que se lea el texto oscuro del logo
    big = size * 2
    disc = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    m = Image.new("L", (big, big), 0)
    r = big * 0.425
    ImageDraw.Draw(m).ellipse((big / 2 - r, big / 2 - r, big / 2 + r, big / 2 + r), fill=255)
    fill = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    for k in range(60):
        rr = r * (1 - k / 60)
        c = tuple(int(lerp(a, b, k / 59)) for a, b in zip((214, 200, 245), (250, 246, 255)))
        fd.ellipse((big / 2 - rr, big / 2 - rr, big / 2 + rr, big / 2 + rr), fill=c + (255,))
    disc.paste(fill, (0, 0), m)
    disc.alpha_composite(LOGO.resize((big, big), Image.LANCZOS))
    return disc.resize((size, size), Image.LANCZOS)


def logo_glow(size):
    lg = logo_with_disc(size)
    pad = size // 4
    a = Image.new("L", (size + pad * 2, size + pad * 2), 0)
    a.paste(lg.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(size // 12))
    g = Image.new("RGBA", a.size, (210, 70, 255, 255))
    g.putalpha(a)
    return lg, g


LOGO_BIG, LOGO_BIG_GLOW = logo_glow(760)
LOGO_MED, LOGO_MED_GLOW = logo_glow(420)
LOGO_SMALL = logo_with_disc(70)


def paste_logo(img, logo, glow, cx, cy, scale, alpha, glow_amt):
    if scale <= 0.01 or alpha <= 0:
        return
    s = (int(logo.width * scale), int(logo.height * scale))
    gs = (int(glow.width * scale), int(glow.height * scale))
    g = with_alpha(glow.resize(gs, Image.BILINEAR), clamp(glow_amt * alpha))
    l = with_alpha(logo.resize(s, Image.BILINEAR), alpha)
    img.alpha_composite(g, (int(cx - gs[0] / 2), int(cy - gs[1] / 2)))
    img.alpha_composite(g, (int(cx - gs[0] / 2), int(cy - gs[1] / 2)))
    img.alpha_composite(l, (int(cx - s[0] / 2), int(cy - s[1] / 2)))


# ---------- escenas ----------
def scene_logo(t, d):
    img = background(t).convert("RGBA")
    p = prog(t, 0.1, 1.0)
    sc = 0.55 + 0.45 * ease_back(p)
    sc *= 1 + 0.015 * math.sin(t * 3)
    # anillo de onda
    rp = prog(t, 0.5, 1.2)
    if 0 < rp < 1:
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r = 300 + 450 * ease_out(rp)
        ImageDraw.Draw(ring).ellipse((W / 2 - r, 820 - r, W / 2 + r, 820 + r),
                                     outline=(236, 120, 255, int(200 * (1 - rp))), width=8)
        img.alpha_composite(ring)
    paste_logo(img, LOGO_BIG, LOGO_BIG_GLOW, W / 2, 820, sc, ease_out(p * 1.5),
               0.6 + 0.3 * math.sin(t * 4))
    put_text(img, "DISEÑO WEB · SEO LOCAL · GOOGLE", "Bold", 40, 1340, 1.2, t,
             color=(244, 114, 182), spacing=4)
    put_text(img, "Tu negocio, en lo más alto", "ExtraBold", 64, 1450, 1.5, t)
    return img


def scene_hook(t, d):
    img = background(t + 10).convert("RGBA")
    put_text(img, "¿Quieres que", "Black", 104, 640, 0.1, t)
    put_text(img, "tu negocio", "Black", 104, 770, 0.3, t)
    put_text(img, "salga el", "Black", 104, 900, 0.5, t)
    put_text(img, "PRIMERO", "Black", 170, 1060, 0.8, t, grad=True, rise=0)
    put_text(img, "en Google?", "Black", 104, 1220, 1.1, t)
    # subrayado animado
    up = ease_out(prog(t, 1.1, 0.6))
    if up > 0:
        bar_w = int(700 * up)
        bar = gradient(max(1, bar_w), 14).convert("RGBA")
        bar.putalpha(round_mask(max(1, bar_w), 14, 7))
        img.alpha_composite(bar, (W // 2 - 350, 1310))
    put_text(img, "Nosotros lo hacemos realidad", "SemiBold", 52, 1460, 1.9, t, color=SOFT)
    footer(img, t)
    return img


# Google: zoom desde la vista general hasta el resultado orgánico
G_CARD = (900, 1200)


def scene_google(t, d):
    img = background(t + 20).convert("RGBA")
    put_text(img, "CASO REAL", "Bold", 40, 200, 0.0, t, color=(244, 114, 182), spacing=6)
    put_text(img, "1º en Google para", "Black", 76, 290, 0.15, t)
    put_text(img, "«cerrajero carabanchel»", "Black", 70, 385, 0.3, t, grad=True)

    z = ease_in_out(prog(t, 1.2, 2.6))
    cw0, ch0, x00, y00 = 1320, 1760, 0, 170
    cw1, ch1 = 1010, 1347
    x01, y01 = 25, 1700 - ch1 / 2
    cw, ch = lerp(cw0, cw1, z), lerp(ch0, ch1, z)
    x0, y0 = lerp(x00, x01, z), lerp(y00, y01, z)
    view = crop_view(GOOGLE, x0, y0, cw, ch, *G_CARD)

    # recuadro sobre el resultado de cerrajerosplanet.es (coords originales)
    hp = ease_out(prog(t, 3.6, 0.6))
    if hp > 0:
        rx0, ry0, rx1, ry1 = 30, 1450, 1300, 1975
        s = G_CARD[0] / cw
        bx0, by0 = (rx0 - x0) * s, (ry0 - y0) * s
        bx1, by1 = (rx1 - x0) * s, (ry1 - y0) * s
        ov = Image.new("RGBA", G_CARD, (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        # oscurecer el resto
        dim = Image.new("RGBA", G_CARD, (10, 5, 30, int(120 * hp)))
        hole = Image.new("L", G_CARD, 255)
        ImageDraw.Draw(hole).rounded_rectangle((bx0, by0, bx1, by1), 24, fill=0)
        dim.putalpha(Image.eval(hole, lambda v: int(v * 120 * hp / 255)))
        view = view.convert("RGBA")
        view.alpha_composite(dim)
        pulse = 1 + 0.5 * math.sin(t * 8)
        od.rounded_rectangle((bx0, by0, bx1, by1), 24,
                             outline=(236, 72, 153, int(255 * hp)), width=int(8 + 2 * pulse))
        view.alpha_composite(ov)

    cp = ease_out(prog(t, 0.2, 0.7))
    paste_card(img, view.convert("RGB"), W / 2, 1110 + (1 - cp) * 200, alpha=cp)

    # insignia Nº1
    bp = prog(t, 3.9, 0.5)
    if bp > 0:
        sc = ease_back(bp)
        pill(img, W / 2, 1640, 520, 120, "Nº1 EN GOOGLE", 56, alpha=clamp(bp * 2), scale=sc)
    footer(img, t)
    return img


def scroll_scene(src, title1, title2, t, d, y_seed, card_h=1180, seed=0):
    img = background(t + seed).convert("RGBA")
    put_text(img, title1, "Black", 74, 230, 0.0, t)
    put_text(img, title2, "Black", 74, 325, 0.15, t, grad=True)
    cw = 860
    s = cw / src.width
    src_h = src.height * s
    view_h_src = card_h / s
    max_scroll = src.height - view_h_src
    sp = ease_in_out(prog(t, 0.8, d - 1.4))
    y0 = max_scroll * sp
    view = crop_view(src, 0, y0, src.width, view_h_src, cw, card_h)
    cp = ease_out(prog(t, 0.1, 0.7))
    paste_card(img, view, W / 2, 1060 + (1 - cp) * 220, scale=0.92 + 0.08 * cp, alpha=cp)
    footer(img, t)
    return img


def scene_cerrajero(t, d):
    img = scroll_scene(CERRAJERO, "Webs que hacen", "sonar el teléfono", t, d, 0, seed=30)
    put_text(img, "cerrajerosplanet.es", "Bold", 44, 1710, 1.0, t, color=SOFT)
    return img


def scene_planet(t, d):
    img = scroll_scene(PLANET_MOBILE, "Tu web profesional,", "rápida y en el móvil", t, d, 0, seed=40)
    return img


FEATURES = ["Diseño web profesional", "SEO local en tu zona",
            "Ficha de Google Maps", "Presupuesto cerrado"]


def scene_features(t, d):
    img = background(t + 50).convert("RGBA")
    put_text(img, "Todo lo que tu", "Black", 84, 330, 0.0, t)
    put_text(img, "negocio necesita", "Black", 84, 430, 0.15, t, grad=True)
    for i, txt in enumerate(FEATURES):
        p = ease_out(prog(t, 0.5 + i * 0.3, 0.55))
        if p <= 0:
            continue
        cy = 640 + i * 175
        x_off = (1 - p) * -300
        panel = Image.new("RGBA", (860, 140), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle((0, 0, 859, 139), 36, fill=(255, 255, 255, 22),
                             outline=(190, 140, 255, 90), width=2)
        # check
        pd.ellipse((30, 30, 110, 110), fill=GREEN)
        pd.line([(50, 72), (65, 88), (92, 54)], fill=(10, 40, 20), width=10, joint="curve")
        lay = text_layer(txt, "Bold", 54)
        panel.alpha_composite(lay, (135, 70 - lay.height // 2 - 4))
        img.alpha_composite(with_alpha(panel, p), (int(110 + x_off), cy - 70))
    bp = prog(t, 2.0, 0.6)
    if bp > 0:
        put_text(img, "Webs desde", "Bold", 54, 1390, 2.0, t, color=SOFT)
        put_text(img, "400 € + IVA", "Black", 130, 1510, 2.15, t, grad=True, rise=0)
    footer(img, t)
    return img


def scene_desk(t, d):
    img = background(t + 60).convert("RGBA")
    put_text(img, "Diseñado en Madrid", "Black", 78, 240, 0.0, t)
    put_text(img, "para toda España", "Black", 78, 340, 0.15, t, grad=True)
    z = ease_in_out(prog(t, 0.0, d))
    cw = lerp(1932, 1300, z)
    ch = cw * 4 / 3
    cx, cy = lerp(966, 760, z), lerp(1288, 950, z)
    x0 = clamp(cx - cw / 2, 0, 1932 - cw)
    y0 = clamp(cy - ch / 2, 0, 2576 - ch)
    view = crop_view(DESK, x0, y0, cw, ch, 900, 1200)
    cp = ease_out(prog(t, 0.05, 0.7))
    paste_card(img, view, W / 2, 1080 + (1 - cp) * 200, alpha=cp)
    footer(img, t)
    return img


def scene_cta(t, d):
    img = background(t + 70).convert("RGBA")
    p = prog(t, 0.0, 0.8)
    paste_logo(img, LOGO_MED, LOGO_MED_GLOW, W / 2, 470, 0.6 + 0.4 * ease_back(p),
               ease_out(p * 1.4), 0.6 + 0.3 * math.sin(t * 4))
    put_text(img, "Pide tu presupuesto", "Black", 84, 830, 0.4, t)
    put_text(img, "sin compromiso", "Black", 84, 935, 0.55, t, grad=True)
    put_text(img, "Te ayudamos a que te encuentren", "SemiBold", 46, 1060, 0.8, t, color=SOFT)
    put_text(img, "y te llamen más clientes", "SemiBold", 46, 1120, 0.9, t, color=SOFT)
    bp = prog(t, 1.2, 0.5)
    if bp > 0:
        pulse = 1 + 0.035 * math.sin(max(0, t - 1.7) * 6)
        pill(img, W / 2, 1340, 820, 150, "serviciosplanet.es", 64,
             alpha=clamp(bp * 2), scale=ease_back(bp) * pulse)
    put_text(img, "Presupuesto y WhatsApp en la web", "Medium", 40, 1510, 1.7, t, color=SOFT)
    return img


SCENES = [
    (scene_logo, 3.2),
    (scene_hook, 3.4),
    (scene_google, 6.0),
    (scene_cerrajero, 4.6),
    (scene_planet, 4.6),
    (scene_features, 4.4),
    (scene_desk, 3.8),
    (scene_cta, 4.2),
]
XF = 0.4  # duración del fundido entre escenas

STARTS = []
_acc = 0.0
for _fn, _d in SCENES:
    STARTS.append(_acc)
    _acc += _d - XF
TOTAL = _acc + XF


def render(i):
    t = i / FPS
    active = []
    for (fn, d), s in zip(SCENES, STARTS):
        if s <= t < s + d:
            active.append((fn, d, t - s))
    frames = []
    for fn, d, lt in active:
        frames.append((fn(lt, d).convert("RGB"), d, lt))
    if len(frames) == 1:
        out = frames[0][0]
    else:
        (a, da, la), (b, db, lb) = frames[0], frames[1]
        out = Image.blend(a, b, ease_in_out(lb / XF))
    # fundido final a negro
    fo = clamp((TOTAL - t) / 0.5)
    if fo < 1:
        out = Image.blend(Image.new("RGB", out.size), out, fo)
    out.save(os.path.join(FRAMES_DIR, f"f{i:05d}.png"), compress_level=1)
    return i


if __name__ == "__main__":
    os.makedirs(FRAMES_DIR, exist_ok=True)
    n = int(TOTAL * FPS)
    only = os.environ.get("ONLY")
    idx = [int(float(x) * FPS) for x in only.split(",")] if only else range(n)
    with Pool(os.cpu_count()) as pool:
        for k, _ in enumerate(pool.imap_unordered(render, idx, chunksize=4)):
            if k % 100 == 0:
                print(f"{k}/{len(idx)}", flush=True)
    if not only:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", os.path.join(FRAMES_DIR, "f%05d.png"),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], check=True)
        print("OK", OUT, f"{TOTAL:.1f}s")
