"""Construction RL demo: the pre-programmed crane lifts and camera moves (Lvl_Construction, LS_Crane).

Writes work/crane_keys.json (every frame, for overlay_crane.py) and work/crane_compact.json (sampled keys Unreal reads).
Crane chain (all relative to the parent): CraneSlew yaw -> TrolleyPivot x -> HookPivot z (+ sway x) -> LoadBeam yaw.
Pick-up: top of the beam stack (3300, -1720). Goal: the glowing slot at (1200, 0, 1120) on the top floor.
"""
import json, math, pathlib

FPS = 30
OUT = pathlib.Path(__file__).parent / 'work'
OUT.mkdir(exist_ok=True)

CX, CY, TZ = 1200.0, -1400.0, 2690.0           # slew centre, trolley height (world)
S0, T0, H0, B0 = -8.66, 2124.0, -2448.0, 8.66   # at the stack: slew yaw, trolley, hook z, beam yaw (beam along world x)
S1, T1, HS, B1 = 90.0, 1400.0, -1445.0, 90.0    # in the slot (beam centre z 1120, along world x)
HANG = -125.0                                   # beam centre below the hook


def ss(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def tl(keys, t, ease=ss):
    """keys: [(t, v)], eased between keys, held outside."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (a, va), (b, vb) in zip(keys, keys[1:]):
        if t <= b:
            return va + (vb - va) * ease((t - a) / (b - a) if b > a else 1)
    return keys[-1][1]


def sway(t, t0, t1, amp, period=3.2):
    if t < t0 or t > t1:
        return 0.0
    env = math.sin(math.pi * (t - t0) / (t1 - t0))
    return amp * env * math.sin(2 * math.pi * (t - t0) / period)


# ---- crane runs, each a function of local time u (seconds) ----
def run_first(u):
    """First try: fast swing, no turn of the beam, lowered while overshooting; hits the top beam at y 800."""
    S = tl([(2.5, S0), (6.5, 96.0)], u)
    T = tl([(2.5, T0), (6.5, 1900.0)], u)
    H = tl([(0.5, H0), (2.5, -900.0), (6.5, -900.0), (8.0, -1400.0)], u)
    X = sway(u, 2.5, 8.0, 85) if u < 8.0 else 6 * math.exp(-(u - 8) * 3) * math.sin((u - 8) * 25)
    return S, T, H, B0, X


def run_pro(u, k=1.0):
    """After practice: smooth lift, beam turned on the way, lowered straight into the slot (placed at u = 14)."""
    u = u * k
    S = tl([(3.0, S0), (11.0, S1)], u)
    T = tl([(3.0, T0), (11.0, T1)], u)
    H = tl([(1.0, H0), (3.0, -1000.0), (11.0, -1000.0), (14.0, HS)], u, ease=lambda x: 1 - (1 - x) ** 2 if x < 1 else 1)
    B = tl([(4.0, B0), (10.0, B1)], u)
    X = sway(u, 3.0, 12.0, 9)
    return S, T, H, B, X


def run_short(u):
    """Practice try 2: stops short of the building and lowers in the open (missed)."""
    S = tl([(0.5, S0), (2.0, 70.0)], u)
    T = tl([(0.5, T0), (2.0, 1500.0)], u)
    H = tl([(0.0, -1100.0), (2.0, -1100.0), (2.8, -1500.0)], u)
    return S, T, H, B0, sway(u, 0.5, 3, 40, 1.6)


def run_tilt(u):
    """Practice try 3: right spot, beam only half turned (not aligned)."""
    S = tl([(0.3, S0), (2.0, S1)], u)
    T = tl([(0.3, T0), (2.0, T1)], u)
    H = tl([(0.0, -1100.0), (2.0, -1100.0), (2.8, -1300.0)], u)
    B = tl([(0.3, B0), (2.0, 50.0)], u)
    return S, T, H, B, sway(u, 0.3, 3, 25, 1.6)


def run_fast_place(u):
    """Practice try 4: placed, a little swing left."""
    S = tl([(0.2, S0), (1.8, S1)], u)
    T = tl([(0.2, T0), (1.8, T1)], u)
    H = tl([(0.0, -1100.0), (1.9, -1100.0), (2.6, HS)], u)
    B = tl([(0.3, B0), (1.7, B1)], u)
    return S, T, H, B, sway(u, 0.2, 2.6, 18, 1.6)


def run_first_fast(u):
    return run_first(u * 8.0 / 3.0)


PLACED = (S1, T1, HS, B1, 0.0)
IDLE = (S0, T0, -2000.0, B0, 0.0)

# Segments (seconds): name, start, end, crane(t_local), camera kind
SEG = [
    ('hook', 0, 12), ('world', 12, 22), ('cad', 22, 28), ('practice', 28, 40), ('pro', 40, 58),
    ('placed', 58, 64), ('wind', 64, 72), ('site', 72, 82), ('close', 82, 90),
]
END = 90
PRACTICE = [(28, 31, run_first_fast), (31, 34, run_short), (34, 37, run_tilt), (37, 40, run_fast_place)]


def crane(t):
    if t < 12:
        return run_first(t)
    if t < 28:
        return IDLE
    if t < 40:
        for a, b, f in PRACTICE:
            if a <= t < b:
                return f(t - a)
    if t < 58:
        return run_pro(t - 40)
    if t < 64:
        return PLACED
    if t < 72:
        u = t - 64
        return (S1, T1, -1250.0, B1, 95 * math.sin(2 * math.pi * u / 3.2) * min(1, u / 1.5))
    if t < 82:
        return run_pro(t - 72)
    return run_pro(t - 82 + 3)


def load_world(t):
    S, T, H, B, X = crane(t)
    r = math.radians(S)
    return (CX + (T + X) * math.cos(r), CY + (T + X) * math.sin(r), TZ + H + HANG)


def look(p, tg):
    dx, dy, dz = tg[0] - p[0], tg[1] - p[1], tg[2] - p[2]
    return (p[0], p[1], p[2], math.degrees(math.atan2(dz, math.hypot(dx, dy))), math.degrees(math.atan2(dy, dx)))


def lerp(a, b, u):
    return [a[i] + (b[i] - a[i]) * u for i in range(len(a))]


def camera_track():
    cam = {}
    sm = None
    for f in range(0, END * FPS + 1):
        t = f / FPS
        L = load_world(t)
        seg = next(s for s in SEG if s[1] <= t < s[2]) if t < END else SEG[-1]
        name, a, b = seg
        u = (t - a) / (b - a)
        if f == round(a * FPS):
            sm = None  # new shot: no smoothing across the cut
        if sm is None:
            sm = list(L)
        k = 1 - math.exp(-(1 / FPS) / 0.45)
        sm = [sm[i] + (L[i] - sm[i]) * k for i in range(3)]
        # Lens: 20 mm on the 23.76 mm filmback (61 degrees wide), set in LS_Crane; overlay_crane.py uses the same.
        if name == 'hook':
            p = lerp((4900, 4300, 2000), (2530, 3680, 1650), ss(min(1, t / 9)))
            tg = lerp((2200, -700, 1000), (1300, 300, 1150), ss(min(1, t / 9)))
            cam[f] = look(p, tg)
        elif name == 'world':
            ang = math.radians(205 + 85 * ss(u))
            p = (1300 + 4700 * math.cos(ang), -700 + 4700 * math.sin(ang), 2500 - 900 * u)
            cam[f] = look(p, (1300, -700, 900))
        elif name == 'cad':
            p = lerp((-400, -3600, 330), (-400, -3060, 275), ss(u))
            cam[f] = look(p, (-400, -2700, 255))
        elif name == 'practice':
            cam[f] = look((2300, -5400, 4600), (2100, -600, 700))
        elif name == 'pro':
            if t < 51:
                p = lerp((5600, 2600, 1700), (3600, 2400, 1900), ss((t - 40) / 11))
                cam[f] = look(p, lerp((2600, -1300, 900), sm, 0.6))
            else:
                p = lerp((2950, 1500, 1700), (2500, 1650, 1550), ss((t - 51) / 7))
                cam[f] = look(p, lerp(sm, (1200, 0, 1120), ss((t - 52) / 4)))
        elif name == 'placed':
            p = lerp((2486, 1532, 1520), (2200, 1732, 1520), ss(u))
            cam[f] = look(p, (1200, 0, 1120))
        elif name == 'wind':
            p = lerp((-700, -1300, 1450), (-550, -1100, 1500), u)
            cam[f] = look(p, (1200, sm[1] * 0.5, 1250))
        elif name == 'site':
            p = lerp((-2600, -4300, 260), (-1100, -3700, 1750), ss(u))
            cam[f] = look(p, lerp((1300, -500, 700), (1200, -1700, 2760), ss(u)))
        else:  # close: near the hook, following the load
            p = lerp((5000, -900, 2100), (4840, -10, 2200), ss(u))
            cam[f] = look(p, sm)
    return cam


def main():
    cam = camera_track()
    every = {}
    for f in range(0, END * FPS + 1):
        S, T, H, B, X = crane(f / FPS)
        every[f] = dict(S=S, T=T, H=H, B=B, X=X, L=load_world(f / FPS), C=cam[f])
    json.dump({'fps': FPS, 'seg': SEG, 'frames': every}, open(OUT / 'crane_keys.json', 'w'))
    cuts = sorted({round(a * FPS) for _, a, _ in SEG[1:]} | {round(a * FPS) for a, _, _ in PRACTICE[1:]})
    frames = set(range(0, END * FPS + 1, 5))
    for c in cuts:
        frames |= {c - 1, c}
    frames = sorted(frames)
    hold = {c - 1 for c in cuts}
    ch = {k: [] for k in ['slew', 'tx', 'hx', 'hz', 'cx', 'cz', 'cp', 'cs', 'by', 'CX', 'CY', 'CZ', 'CP', 'CW']}
    prev = None
    for f in frames:
        S, T, H, B, X = crane(f / FPS)
        L = max(50.0, -H)
        ch['slew'].append(S); ch['tx'].append(T); ch['hx'].append(X); ch['hz'].append(H)
        ch['cx'].append(X / 2); ch['cz'].append(H / 2); ch['cp'].append(math.degrees(math.asin(max(-1, min(1, X / L)))))
        ch['cs'].append(L / 100); ch['by'].append(B)
        c = cam[f]
        w = c[4]
        if prev is not None:
            while w - prev > 180: w -= 360
            while w - prev < -180: w += 360
        prev = w
        ch['CX'].append(c[0]); ch['CY'].append(c[1]); ch['CZ'].append(c[2]); ch['CP'].append(c[3]); ch['CW'].append(w)
    comp = {'f': frames, 'cut': sorted(hold), **{k: [round(v, 2) for v in vs] for k, vs in ch.items()}}
    json.dump(comp, open(OUT / 'crane_compact.json', 'w'))
    print(len(frames), 'frames sampled,', len(frames) * len(ch), 'keys')


if __name__ == '__main__':
    main()
