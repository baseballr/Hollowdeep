"""Hollowdeep art toolkit: palettes, pixel painters, box-UV geometry builder, and a preview renderer."""
import colorsys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- colour
def hx(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255], dtype=float)

def ramp(base, n=6, dark=0.32, light=0.35, hue_shift=0.06, sat_bias=0.1):
    """Hue-shifted shade ramp, dark -> light, base in the middle. Shadows drift cool, highlights warm."""
    r, g, b = [c / 255 for c in hx(base)[:3]]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    out = []
    for i in range(n):
        t = i / (n - 1) * 2 - 1  # -1..1
        if t < 0:
            L = l + t * min(dark, l * 0.85)
            H = h + (-t) * hue_shift * (1 if (h < 0.17 or h > 0.67) else -1) * 0.5
            H = h - (-t) * hue_shift if 0.08 < h < 0.6 else h + (-t) * hue_shift * 0.5
            S = min(1, s + (-t) * sat_bias)
        else:
            L = l + t * min(light, (1 - l) * 0.9)
            H = h + t * hue_shift * (1 if 0.17 < h < 0.6 else -1) * 0.5
            S = max(0, s - t * sat_bias * 0.6)
        rr, gg, bb = colorsys.hls_to_rgb(H % 1, max(0, min(1, L)), max(0, min(1, S)))
        out.append(np.array([rr * 255, gg * 255, bb * 255, 255]))
    return out

def mix(a, b, t):
    return a * (1 - t) + b * t

# ---------------------------------------------------------------- painters
# A painter is f(a, ctx) where a is an (h, w, 4) float view of the texture, ctx has face/cube info and rng.

class Ctx:
    def __init__(self, face, w, h, cube, rng):
        self.face, self.w, self.h, self.cube, self.rng = face, w, h, cube, rng

def put(a, x, y, c):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = c

def idx_paint(a, idx, R):
    idx = np.clip(np.round(idx).astype(int), 0, len(R) - 1)
    for i, c in enumerate(R):
        a[idx == i] = c

def edge_dist(h, w):
    ys, xs = np.mgrid[0:h, 0:w]
    return np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))

def blotch(rng, h, w, scale=3, amp=1.0):
    """Cheap value noise: random grid upsampled with nearest + jitter."""
    gh, gw = h // scale + 2, w // scale + 2
    g = rng.normal(0, amp, (gh, gw))
    ys, xs = np.mgrid[0:h, 0:w]
    fy, fx = ys / scale, xs / scale
    y0, x0 = fy.astype(int), fx.astype(int)
    ty, tx = fy - y0, fx - x0
    v = (g[y0, x0] * (1 - tx) * (1 - ty) + g[y0, x0 + 1] * tx * (1 - ty) + g[y0 + 1, x0] * (1 - tx) * ty + g[y0 + 1, x0 + 1] * tx * ty)
    return v

def vpos(ctx):
    """World-height fraction (0 bottom, 1 top) for every row of the face, for gradients that agree across cubes."""
    y0, y1 = ctx.cube['y0'], ctx.cube['y1']
    h = ctx.h
    if ctx.face in ('up',):
        return np.full((h, 1), 1.0)
    if ctx.face in ('down',):
        return np.full((h, 1), 0.0)
    rows = np.arange(h)[:, None]
    return 1 - (rows + 0.5) / max(h, 1)

def base_shade(ctx, mid, edge=1, grad=0.8, noise=0.7, scale=2, ao=True):
    """Index map around `mid` with a vertical gradient, noise and darkened edges."""
    h, w = ctx.h, ctx.w
    idx = np.full((h, w), float(mid))
    idx += (vpos(ctx) - 0.5) * grad
    idx += blotch(ctx.rng, h, w, scale, noise * 0.7) + ctx.rng.normal(0, noise * 0.35, (h, w))
    if ctx.face == 'up':
        idx += 0.6
    if ctx.face == 'down':
        idx -= 0.8
    if ao and edge:
        d = edge_dist(h, w)
        idx -= (d < edge) * 0.8
    return idx

def M_solid(R, mid=3, **kw):
    def p(a, ctx):
        idx_paint(a, base_shade(ctx, mid, **kw), R)
    return p

def M_flesh(R, mid=3, spots=0.04, vein=None):
    def p(a, ctx):
        idx = base_shade(ctx, mid, noise=0.55, scale=2)
        m = ctx.rng.random((ctx.h, ctx.w)) < spots
        idx[m] -= 1.3
        idx_paint(a, idx, R)
        if vein is not None and ctx.h > 4:
            for _ in range(max(1, ctx.w * ctx.h // 60)):
                x, y = ctx.rng.integers(0, ctx.w), ctx.rng.integers(0, ctx.h)
                for _ in range(ctx.rng.integers(2, 5)):
                    put(a, x, y, vein)
                    x += ctx.rng.integers(-1, 2); y += 1
    return p

def M_cloth(R, mid=3, fold=4, hem=None, fray=False, trim=None):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.4, scale=3, grad=0.6)
        if ctx.face not in ('up', 'down'):
            ph = ctx.rng.random() * 6
            cols = np.arange(w)
            f = np.sin((cols + ph) * 2 * math.pi / fold)
            idx += np.where(f > 0.55, 0.9, np.where(f < -0.6, -0.9, 0))[None, :]
        idx_paint(a, idx, R)
        if ctx.face not in ('up', 'down'):
            if trim is not None and h > 3:
                a[h - 2:h, :] = trim
                for x in range(0, w, 2):
                    put(a, x, h - 2, mix(trim, np.array([255, 255, 255, 255.]), 0.35))
            if fray and h > 4:
                for x in range(w):
                    if ctx.rng.random() < 0.45:
                        a[h - 1, x, 3] = 0
                        if ctx.rng.random() < 0.4:
                            a[h - 2, x, 3] = 0
    return p

def M_metal(R, mid=3, rivets=True, bevel=True, scratches=0.03, rust=None, rust_amt=0.0):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.35, scale=3, grad=0.5, ao=False)
        if bevel and ctx.face != 'down':
            ys, xs = np.mgrid[0:h, 0:w]
            idx[ys == 0] += 1.2
            idx[xs == 0] += 0.6
            idx[ys == h - 1] -= 1.2
            idx[xs == w - 1] -= 0.8
        m = ctx.rng.random((h, w)) < scratches
        idx[m] += 1.5
        idx_paint(a, idx, R)
        if rust is not None and rust_amt > 0:
            rm = (blotch(ctx.rng, h, w, 2, 1) > 1 - rust_amt * 2)
            a[rm] = mix(a[rm], rust, 0.75)
        if rivets and ctx.face not in ('up', 'down') and w >= 4 and h >= 4:
            for (x, y) in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)):
                put(a, x, y, R[-1]);
                put(a, x + 1, y + 1, R[0]) if x + 1 < w - 1 else None
    return p

def M_bone(R, mid=4, cracks=0.5):
    def p(a, ctx):
        idx = base_shade(ctx, mid, noise=0.5, scale=2, grad=0.5, edge=1)
        idx_paint(a, idx, R)
        h, w = ctx.h, ctx.w
        for _ in range(int(cracks * (w * h) / 20) + (1 if cracks else 0)):
            x, y = ctx.rng.integers(0, w), ctx.rng.integers(0, h)
            for _ in range(ctx.rng.integers(1, 4)):
                put(a, x, y, R[1]); x += ctx.rng.integers(-1, 2); y += ctx.rng.integers(0, 2)
    return p

def M_bark(R, mid=3, knots=True, moss=None, moss_amt=0.0):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.35, scale=3, grad=0.4)
        if ctx.face not in ('up', 'down'):
            for x in range(w):
                y = ctx.rng.integers(-3, h)
                L = ctx.rng.integers(3, max(4, h))
                idx[max(0, y):min(h, y + L), x] -= 1.3 if ctx.rng.random() < 0.55 else -0.7
        else:
            ys, xs = np.mgrid[0:h, 0:w]
            r = np.hypot(ys - h / 2 + 0.5, xs - w / 2 + 0.5)
            idx += np.where((r.astype(int) % 2) == 0, 0.5, -0.4)
        idx_paint(a, idx, R)
        if knots and ctx.face not in ('up', 'down') and w > 3 and h > 5:
            for _ in range(max(1, w * h // 70)):
                x, y = ctx.rng.integers(1, w - 1), ctx.rng.integers(1, h - 2)
                put(a, x, y, R[0]); put(a, x, y + 1, R[1]); put(a, x - 1, y, R[1]); put(a, x + 1, y + 1, R[2])
        if moss is not None and moss_amt > 0:
            b = blotch(ctx.rng, h, w, 2, 1) + (vpos(ctx) - 0.3) * 1.5 * (1 if ctx.face != 'down' else 0)
            if ctx.face == 'up':
                b = b + 2
            m = b > (1.2 - moss_amt * 2.4)
            midx = np.clip(2 + blotch(ctx.rng, h, w, 1, 0.9), 0, len(moss) - 1)
            tmp = np.zeros_like(a)
            idx_paint(tmp, midx, moss)
            a[m] = tmp[m]
    return p

def M_ice(R, mid=3, streaks=True, cracks=True):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.3, scale=3, grad=0.9, ao=True)
        if streaks:
            ys, xs = np.mgrid[0:h, 0:w]
            k = ctx.rng.integers(0, 7)
            band = ((xs + ys + k) % 7 == 0) | ((xs + ys + k) % 11 == 0)
            idx[band] += 1.4
        idx_paint(a, idx, R)
        if cracks and w * h > 12:
            for _ in range(max(1, w * h // 50)):
                x, y = ctx.rng.integers(0, w), ctx.rng.integers(0, h)
                for _ in range(ctx.rng.integers(2, 5)):
                    put(a, x, y, R[-1]); x += 1; y += ctx.rng.integers(0, 2)
    return p

def M_moss(R, mid=3, flowers=None, flower_rate=0.03):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=1.1, scale=1, grad=0.8)
        idx_paint(a, idx, R)
        if flowers and ctx.face != 'down':
            for _ in range(int(w * h * flower_rate) + 1):
                if ctx.rng.random() < 0.6:
                    x, y = ctx.rng.integers(0, w), ctx.rng.integers(0, h)
                    put(a, x, y, flowers[ctx.rng.integers(0, len(flowers))])
    return p

def M_hanging(R, mid=3, top_solid=2, density=0.7, base=None):
    """Hanging fringe (moss, rags, icicles) for overlay cubes: solid top rows, ragged drips below."""
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        (base or M_moss(R, mid))(a, ctx)
        if ctx.face in ('up',):
            return
        if ctx.face == 'down':
            a[..., 3] = 0
            return
        for x in range(w):
            L = top_solid + int(ctx.rng.random() ** (1 / density) * (h - top_solid))
            a[L:, x, 3] = 0
    return p

def M_planks(R, mid=3, plank=4, vertical=False):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.35, scale=4, grad=0.3, ao=False)
        ys, xs = np.mgrid[0:h, 0:w]
        q = xs if vertical else ys
        o = ys if vertical else xs
        row = q // plank
        idx += (row % 2) * 0.35
        idx[(q % plank) == plank - 1] -= 1.6
        grain = ctx.rng.random((h, w)) < 0.12
        idx[grain] -= 0.9
        # stagger seams
        for r in range(row.max() + 1):
            sx = ctx.rng.integers(2, 12)
            seam = ((o - sx) % 14 == 0) & (row == r)
            idx[seam] -= 1.0
        idx_paint(a, idx, R)
    return p

def M_crack(R, crackR, mid=2, density=1.0, glow_core=True):
    """Dark rock/iron with glowing fissures (lava, souls, frost)."""
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        idx = base_shade(ctx, mid, noise=0.6, scale=2, grad=0.5)
        idx_paint(a, idx, R)
        n = int(max(1, w * h / 45) * density)
        for _ in range(n):
            x, y = ctx.rng.integers(0, w), ctx.rng.integers(0, h)
            L = ctx.rng.integers(4, 10)
            dx = ctx.rng.choice([-1, 1])
            for i in range(L):
                c = crackR[-1] if (glow_core and 1 < i < L - 2 and ctx.rng.random() < 0.3) else crackR[len(crackR) // 2 - 1 + (i % 2)]
                put(a, x, y, c)
                if ctx.rng.random() < 0.6:
                    y += 1
                    x += dx if ctx.rng.random() < 0.5 else 0
                else:
                    x += dx
    return p

def M_fire(R, mid=3):
    """R runs dark red -> white-yellow. Bright at the bottom, flickering darker tongues toward the top."""
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        v = vpos(ctx)
        idx = (1 - v) * (len(R) - 1) * 0.9 + 0.6 + blotch(ctx.rng, h, w, 2, 1.2)
        if ctx.face == 'up':
            idx = np.full((h, w), 1.5) + blotch(ctx.rng, h, w, 1, 1)
        idx_paint(a, idx, R)
    return p

def M_crystal(R, mid=3):
    def p(a, ctx):
        h, w = ctx.h, ctx.w
        ys, xs = np.mgrid[0:h, 0:w]
        idx = mid + (xs / max(w - 1, 1) - ys / max(h - 1, 1)) * 1.6 + (vpos(ctx) - 0.5) * 0.6
        idx[(xs + ys) % 5 == 0] += 0.8
        idx[edge_dist(h, w) == 0] -= 1
        idx_paint(a, idx, R)
        put(a, 1, 1, R[-1]); put(a, 2, 1, R[-1]); put(a, 1, 2, R[-1])
    return p

def M_none():
    def p(a, ctx):
        a[..., 3] = 0
    return p

def M_glow(c, rim=None):
    def p(a, ctx):
        a[...] = c
        if rim is not None:
            a[edge_dist(ctx.h, ctx.w) == 0] = rim
    return p

def stamp(art, pal, ox=0, oy=0, anchor=None):
    """Decorator: draw ASCII pixel art onto a face. '.' keeps, ' ' keeps, '_' clears alpha."""
    lines = [l for l in art.strip('\n').split('\n')]
    def p(a, ctx):
        h, w = a.shape[:2]
        ah, aw = len(lines), max(len(l) for l in lines)
        x0, y0 = ox, oy
        if anchor == 'center':
            x0, y0 = (w - aw) // 2 + ox, (h - ah) // 2 + oy
        elif anchor == 'top':
            x0, y0 = (w - aw) // 2 + ox, oy
        elif anchor == 'bottom':
            x0, y0 = (w - aw) // 2 + ox, h - ah + oy
        for y, l in enumerate(lines):
            for x, ch in enumerate(l):
                if ch in '. ':
                    continue
                if ch == '_':
                    if 0 <= y0 + y < h and 0 <= x0 + x < w:
                        a[y0 + y, x0 + x, 3] = 0
                    continue
                put(a, x0 + x, y0 + y, hx(pal[ch]) if isinstance(pal[ch], str) else pal[ch])
    return p

def chain(*ps):
    def p(a, ctx):
        for f in ps:
            if f is not None:
                f(a, ctx)
    return p

def hband(y, hgt, c, faces=None, dots=None):
    """Horizontal band across side faces at face row y (negative = from bottom)."""
    def p(a, ctx):
        if ctx.face in ('up', 'down'):
            return
        yy = y if y >= 0 else ctx.h + y
        a[max(0, yy):yy + hgt, :] = c
        if hgt > 1:
            a[max(0, yy), :] = mix(c, np.array([255, 255, 255, 255.]), 0.3)
            a[min(ctx.h - 1, yy + hgt - 1), :] = mix(c, np.array([0, 0, 0, 255.]), 0.35)
        if dots is not None:
            for x in range(1, ctx.w, 3):
                put(a, x, yy + hgt // 2, dots)
    return p

def vband(x, wid, c, faces=('north',)):
    def p(a, ctx):
        if ctx.face not in faces:
            return
        xx = x if x >= 0 else ctx.w + x
        a[:, max(0, xx):xx + wid] = c
    return p

def only(faces, f):
    def p(a, ctx):
        if ctx.face in faces:
            f(a, ctx)
    return p

def sprinkle(c, rate, faces=None, avoid_alpha=True):
    def p(a, ctx):
        if faces and ctx.face not in faces:
            return
        m = ctx.rng.random(a.shape[:2]) < rate
        if avoid_alpha:
            m &= a[..., 3] > 0
        a[m] = c
    return p

# ---------------------------------------------------------------- geometry
FACES = ('north', 'south', 'east', 'west', 'up', 'down')

class Model:
    def __init__(self, ident, tex_w=128, tex_h=None):
        self.ident = ident
        self.bones = {}
        self.order = []
        self.cubes = []
        self.tex_w = tex_w
        self.tex_h = tex_h

    def bone(self, name, parent=None, pivot=(0, 0, 0)):
        self.bones[name] = {'name': name, 'parent': parent, 'pivot': list(pivot)}
        self.order.append(name)
        return name

    def cube(self, bone, origin, size, paint=None, faces=None, inflate=0, seed=None, mirror=False):
        """paint: default painter; faces: dict face->painter (overrides, or chain with '+face' keys)."""
        c = dict(bone=bone, origin=list(origin), size=list(size), paint=paint, faces=faces or {},
                 inflate=inflate, seed=seed if seed is not None else len(self.cubes) * 7919 + 13)
        self.cubes.append(c)
        return c

    # ---- packing
    def pack(self):
        items = []
        for c in self.cubes:
            w, h, d = [math.ceil(v) for v in c['size']]
            c['_wh'] = (2 * (d + w), d + h)
            items.append(c)
        W = self.tex_w
        order = sorted(items, key=lambda c: -c['_wh'][1])
        x = y = rowh = 0
        for c in order:
            fw, fh = c['_wh']
            if fw > W:
                raise ValueError(f'{self.ident}: cube too wide for texture {fw}>{W}')
            if x + fw > W:
                x, y, rowh = 0, y + rowh, 0
            c['uv'] = [x, y]
            x += fw
            rowh = max(rowh, fh)
        H = y + rowh
        th = 16
        while th < H:
            th *= 2
        self.tex_h = max(self.tex_h or 0, th)

    def face_regions(self, c):
        u, v = c['uv']
        w, h, d = [math.ceil(s) for s in c['size']]
        return {
            'east': (u, v + d, d, h), 'north': (u + d, v + d, w, h), 'west': (u + d + w, v + d, d, h),
            'south': (u + 2 * d + w, v + d, w, h), 'up': (u + d, v, w, d), 'down': (u + d + w, v, w, d),
        }

    def paint(self):
        self.pack()
        tex = np.zeros((self.tex_h, self.tex_w, 4))
        for c in self.cubes:
            x0, y0, z0 = c['origin']
            sx, sy, sz = c['size']
            info = dict(x0=x0, y0=y0, z0=z0, x1=x0 + sx, y1=y0 + sy, z1=z0 + sz)
            for f, (u, v, w, h) in self.face_regions(c).items():
                if w == 0 or h == 0:
                    continue
                rng = np.random.default_rng(c['seed'] * 31 + FACES.index(f))
                ctx = Ctx(f, w, h, info, rng)
                a = tex[v:v + h, u:u + w]
                p = c['faces'].get(f, c['paint'])
                if p is not None:
                    p(a, ctx)
                extra = c['faces'].get('+' + f)
                if extra is not None:
                    extra(a, ctx)
                extra = c['faces'].get('+all')
                if extra is not None:
                    extra(a, ctx)
        self.tex = np.clip(tex, 0, 255).astype(np.uint8)
        return self.tex

    def geo_json(self, bounds=(4, 4.5)):
        bones = []
        for n in self.order:
            b = self.bones[n]
            jb = {'name': n, 'pivot': b['pivot']}
            if b['parent']:
                jb['parent'] = b['parent']
            cubes = []
            for c in self.cubes:
                if c['bone'] != n:
                    continue
                jc = {'origin': [round(v, 3) for v in c['origin']], 'size': c['size'], 'uv': c['uv']}
                if c['inflate']:
                    jc['inflate'] = c['inflate']
                cubes.append(jc)
            if cubes:
                jb['cubes'] = cubes
            bones.append(jb)
        return {'format_version': '1.12.0', 'minecraft:geometry': [{
            'description': {'identifier': self.ident, 'texture_width': self.tex_w, 'texture_height': self.tex_h,
                            'visible_bounds_width': bounds[0], 'visible_bounds_height': bounds[1],
                            'visible_bounds_offset': [0, bounds[1] / 2, 0]},
            'bones': bones}]}

def model_from_geo(path_or_dict, tex_png):
    d = json.load(open(path_or_dict)) if isinstance(path_or_dict, str) else path_or_dict
    g = d['minecraft:geometry'][0]
    m = Model(g['description']['identifier'], g['description']['texture_width'], g['description']['texture_height'])
    for b in g['bones']:
        m.bone(b['name'], b.get('parent'), b.get('pivot', [0, 0, 0]))
        for c in b.get('cubes', []):
            cc = m.cube(b['name'], c['origin'], c['size'], inflate=c.get('inflate', 0))
            cc['uv'] = c['uv']
    im = Image.open(tex_png).convert('RGBA')
    m.tex_w, m.tex_h = g['description']['texture_width'], g['description']['texture_height']
    m.tex = np.array(im.resize((m.tex_w, m.tex_h), Image.NEAREST))
    return m

# ---------------------------------------------------------------- renderer
def _rot(p, piv, r):
    p = np.array(p, float) - piv
    rx, ry, rz = [math.radians(a) for a in r]
    if rx:
        y, z = p[1] * math.cos(rx) - p[2] * math.sin(rx), p[1] * math.sin(rx) + p[2] * math.cos(rx); p[1], p[2] = y, z
    if ry:
        x, z = p[0] * math.cos(ry) + p[2] * math.sin(ry), -p[0] * math.sin(ry) + p[2] * math.cos(ry); p[0], p[2] = x, z
    if rz:
        x, y = p[0] * math.cos(rz) - p[1] * math.sin(rz), p[0] * math.sin(rz) + p[1] * math.cos(rz); p[0], p[1] = x, y
    return p + piv

def render(model, size=360, yaw=-32, pitch=16, scale=None, emissive=False, bg=None, ss=2, pose=None):
    """Orthographic textured render with Minecraft-style face lighting. Returns RGBA PIL image."""
    tex = model.tex.astype(float)
    TH, TW = tex.shape[:2]
    S = size * ss
    cy, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    pose = pose or {}
    def posed(p, bone):
        b = bone
        while b:
            if b in pose:
                p = _rot(p, np.array(model.bones[b]['pivot'], float), pose[b])
            b = model.bones[b]['parent']
        return p

    def view(p):
        x, y, z = -p[0], p[1], p[2]  # mirror x into a right-handed frame
        x, z = x * cy + z * sy_, -x * sy_ + z * cy
        y, z = y * cp + z * sp, -y * sp + z * cp
        return np.array([x, y, z])

    # bounds
    pts = []
    for c in model.cubes:
        i = c['inflate']; o = np.array(c['origin']) - i; s = np.array(c['size']) + 2 * i
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    pts.append(view(posed(o + s * np.array([dx, dy, dz]), c['bone'])))
    pts = np.array(pts)
    mn, mx = pts.min(0), pts.max(0)
    span = max(mx[0] - mn[0], mx[1] - mn[1]) * 1.08
    k = scale * ss if scale else S / span
    cx, cyy = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2
    img = np.zeros((S, S, 4))
    if bg is not None:
        img[:] = bg
    zbuf = np.full((S, S), -1e9)
    light = {'north': 0.86, 'south': 0.62, 'east': 0.7, 'west': 0.92, 'up': 1.0, 'down': 0.5}
    for c in model.cubes:
        i = c['inflate']
        x0, y0, z0 = np.array(c['origin']) - i
        x1, y1, z1 = np.array(c['origin']) + np.array(c['size']) + i
        regs = model.face_regions(c)
        corners = {
            'north': ((x0, y1, z0), (x1, y1, z0), (x0, y0, z0)),
            'south': ((x1, y1, z1), (x0, y1, z1), (x1, y0, z1)),
            'east': ((x0, y1, z1), (x0, y1, z0), (x0, y0, z1)),
            'west': ((x1, y1, z0), (x1, y1, z1), (x1, y0, z0)),
            'up': ((x0, y1, z1), (x1, y1, z1), (x0, y1, z0)),
            'down': ((x0, y0, z0), (x1, y0, z0), (x0, y0, z1)),
        }
        for f, (TL, TR, BL) in corners.items():
            u, v, w, h = regs[f]
            if w == 0 or h == 0:
                continue
            A, B, C = [view(posed(np.array(q, float), c['bone'])) for q in (TL, TR, BL)]
            e1, e2 = B - A, C - A
            n = np.cross(e1, e2)
            if abs(n[2]) < 1e-9:
                continue
            # screen coords
            def scr(P):
                return np.array([(P[0] - cx) * k + S / 2, -(P[1] - cyy) * k + S / 2])
            a2, b2, c2 = scr(A), scr(B), scr(C)
            d2 = b2 + c2 - a2
            xs = [a2[0], b2[0], c2[0], d2[0]]; ys = [a2[1], b2[1], c2[1], d2[1]]
            bx0, bx1 = max(0, int(min(xs))), min(S - 1, int(max(xs)) + 1)
            by0, by1 = max(0, int(min(ys))), min(S - 1, int(max(ys)) + 1)
            if bx1 <= bx0 or by1 <= by0:
                continue
            E1, E2 = b2 - a2, c2 - a2
            det = E1[0] * E2[1] - E1[1] * E2[0]
            if abs(det) < 1e-9:
                continue
            gy, gx = np.mgrid[by0:by1 + 1, bx0:bx1 + 1]
            px, py = gx + 0.5 - a2[0], gy + 0.5 - a2[1]
            s = (px * E2[1] - py * E2[0]) / det
            t = (E1[0] * py - E1[1] * px) / det
            m = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
            if not m.any():
                continue
            z = A[2] + s * e1[2] + t * e2[2]
            front_facing = n[2] < 0  # toward viewer (viewer at -z)
            tu = np.clip((u + s * w).astype(int), 0, TW - 1)
            tv = np.clip((v + t * h).astype(int), 0, TH - 1)
            col = tex[tv, tu]
            m &= col[..., 3] > 127
            depth = -z
            m &= depth > zbuf[by0:by1 + 1, bx0:bx1 + 1] + (0 if front_facing else -1e-3)
            if not front_facing:
                # back faces only matter for zero-thickness planes; dim them
                pass
            lit = 1.0 if emissive else light[f]
            rgb = col[..., :3] * lit
            sub = img[by0:by1 + 1, bx0:bx1 + 1]
            sub[m, :3] = rgb[m]
            sub[m, 3] = 255
            zb = zbuf[by0:by1 + 1, bx0:bx1 + 1]
            zb[m] = depth[m]
    im = Image.fromarray(img.astype(np.uint8), 'RGBA')
    if ss > 1:
        im = im.resize((size, size), Image.LANCZOS)
    return im

def font(sz):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
        try:
            return ImageFont.truetype(f, sz)
        except Exception:
            pass
    return ImageFont.load_default()
