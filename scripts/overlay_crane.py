"""Construction RL demo: draws the branded LIFT SCORECARD on the rendered crane frames, cuts the clips (NVENC),
builds the side-by-side clip and the slide stills.

python overlay_crane.py
"""
import json, math, pathlib, subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).parent
# Frames from render.py (its output folder has no spaces; Unreal writes nothing to a folder with spaces).
FR = pathlib.Path(r"C:\rlfilm\LS_Crane_full")
OUT_FR = HERE / 'work' / 'crane_ov'
SLUG = 'rl-environment-tower-crane-construction'
VID = pathlib.Path(r"output") / f'2026-11-02_{SLUG}'
CLIPS = VID / 'clips'
STILLS = pathlib.Path(r"output\stills") / SLUG
FPS = 30
K = json.load(open(HERE / 'work' / 'crane_keys.json'))['frames']
LOGO = Image.open(HERE / 'brand' / 'logo120.png').convert('RGBA')
NAVY = (23, 32, 44); YEL = (255, 216, 77); WHITE = (251, 251, 249); GREY = (201, 209, 217)
RED = (229, 72, 77); GREEN = (63, 185, 80)
F = lambda w, s: ImageFont.truetype({'b': 'C:/Windows/Fonts/segoeuib.ttf', 's': 'C:/Windows/Fonts/seguisb.ttf'}[w], s)
f_pill, f_lab, f_big, f_val, f_pop, f_ban, f_shop = F('b', 24), F('s', 20), F('b', 64), F('b', 34), F('b', 40), F('b', 40), F('b', 36)
logo_s = LOGO.resize((int(LOGO.width * 44 / LOGO.height), 44), Image.LANCZOS)
SLOT = (1200.0, 0.0, 1120.0)
START = (3300.0, -1720.0, 117.0)
D0 = math.dist(START, SLOT)


def k(t):
    return K[str(max(0, min(len(K) - 1, round(t * FPS))))]


def progress(t):
    return max(0.0, min(1.0, 1 - math.dist(k(t)['L'], SLOT) / D0))


def align(t):
    return max(0.0, min(1.0, 1 - abs(k(t)['B'] - 90) / 81.34))


TRIES = [(28, 31, 30.7, 'HIT  -30', RED), (31, 34, 33.4, 'MISSED', RED), (34, 37, 36.4, 'NOT ALIGNED', RED), (37, 40, 39.2, 'PLACED  +20', GREEN)]


def state(t):
    if t < 12:
        hit = t >= 8.0
        score = int(60 * progress(min(t, 8.0))) - (30 if hit else 0)
        return dict(mode='FIRST TRY' if t < 8.6 else 'FAILED', mcol=RED, score=score, scol=RED if score < 0 else WHITE,
                    rows=[('TIME', f'{min(t, 8.0):0.1f} s'), ('HITS', '1' if hit else '0')],
                    pop='HIT  -30' if 8.0 <= t < 9.4 else '')
    if 28 <= t < 40:
        u = (t - 28) / 12
        tries = int(1 + 3199 * u ** 2.2)
        best = int(-30 + 125 * (1 - (1 - u) ** 2.5))
        pop, pc = '', RED
        for a, b, at, txt, col in TRIES:
            if at <= t < b:
                pop, pc = txt, col
        return dict(mode='PRACTICE, SPED UP', mcol=YEL, score=best, scol=YEL, score_label='BEST SCORE',
                    rows=[('TRIES', f'{tries:,}'), ('SPEED', '40x')], pop=pop, pop_col=pc)
    if 40 <= t < 64 or 82 <= t < 90:
        lt = t - 40 if t < 64 else t - 82 + 3
        done = lt >= 14.0
        tt = t if t < 64 else t - 82 + 43
        score = int(60 * progress(tt) + 20 * align(tt)) + (20 if done else 0)
        if done:
            score = 100
        mode = 'PLACED' if done else ('AFTER PRACTICE' if t < 64 else 'LEARNING')
        return dict(mode=mode, mcol=GREEN, score=score, scol=GREEN, rows=[('TIME', f'{min(lt, 14.0):0.1f} s'), ('HITS', '0')],
                    pop='PLACED  +20' if 14.0 <= lt < 15.4 else '', pop_col=GREEN, banner=lt >= 14.6)
    if 64 <= t < 72:
        x = abs(k(t)['X'])
        return dict(mode='WIND GUST', mcol=YEL, score=f'{x:0.0f} cm', scol=YEL, score_label='LOAD SWAY',
                    rows=[('WIND', 'GUST'), ('HITS', '0')], pop='')
    return None


def rr(d, box, r, fill):
    d.rounded_rectangle(box, r, fill=fill)


TAN_HALF = 23.76 / 2 / 20  # 20 mm lens on the 23.76 mm filmback (LS_Crane camera)


def project(c, P):
    """Screen pixel of world point P for camera c = (x, y, z, pitch, yaw)."""
    p, w = math.radians(c[3]), math.radians(c[4])
    f = (math.cos(p) * math.cos(w), math.cos(p) * math.sin(w), math.sin(p))
    r = (-math.sin(w), math.cos(w), 0)
    u = (-math.sin(p) * math.cos(w), -math.sin(p) * math.sin(w), math.cos(p))
    dv = (P[0] - c[0], P[1] - c[1], P[2] - c[2])
    df = sum(a * b for a, b in zip(dv, f))
    return (960 + 960 * sum(a * b for a, b in zip(dv, r)) / (df * TAN_HALF),
            540 - 960 * sum(a * b for a, b in zip(dv, u)) / (df * TAN_HALF))


def topdown_ring(d, t):
    px, py = project(k(t)['C'], k(t)['L'])
    d.ellipse((px - 58, py - 58, px + 58, py + 58), outline=NAVY + (255,), width=12)
    d.ellipse((px - 56, py - 56, px + 56, py + 56), outline=YEL + (255,), width=8)
    tw = d.textlength('BEAM', font=f_pill)
    rr(d, (px - tw / 2 - 14, py - 108, px + tw / 2 + 14, py - 70), 16, YEL)
    d.text((px - tw / 2, py - 106), 'BEAM', font=f_pill, fill=NAVY)


def draw(im, t):
    st = state(t)
    if not st:
        return im
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if 28 <= t < 40:
        topdown_ring(d, t)
    x0, y0, w, h = 1452, 48, 420, 330
    rr(d, (x0, y0, x0 + w, y0 + h), 18, NAVY + (232,))
    d.rectangle((x0, y0 + 14, x0 + 6, y0 + h - 14), fill=YEL)
    ov.alpha_composite(logo_s, (x0 + 22, y0 + 18))
    d.text((x0 + 30 + logo_s.width, y0 + 12), 'TOWER CRANE', font=f_shop, fill=YEL)
    d.text((x0 + 32 + logo_s.width, y0 + 52), 'LIFT SCORECARD', font=f_lab, fill=GREY)
    tw = d.textlength(st['mode'], font=f_pill)
    rr(d, (x0 + 22, y0 + 84, x0 + 22 + tw + 32, y0 + 124), 20, st['mcol'])
    d.text((x0 + 38, y0 + 88), st['mode'], font=f_pill, fill=WHITE if st['mcol'] == RED else NAVY)
    d.text((x0 + 24, y0 + 138), st.get('score_label', 'SCORE'), font=f_lab, fill=GREY)
    d.text((x0 + 22, y0 + 158), str(st['score']), font=f_big, fill=st['scol'])
    for i, (lab, val) in enumerate(st['rows']):
        cx = x0 + 22 + i * 200
        d.text((cx, y0 + 248), lab, font=f_lab, fill=GREY)
        d.text((cx, y0 + 270), val, font=f_val, fill=WHITE)
    if st['pop']:
        pf = f_pop if d.textlength(st['pop'], font=f_pop) < 180 else f_pill
        pw = d.textlength(st['pop'], font=pf) + 28
        col = st.get('pop_col', RED)
        rr(d, (x0 + w - 18 - pw, y0 + 162, x0 + w - 18, y0 + 224), 12, col)
        d.text((x0 + w - 4 - pw, y0 + (168 if pf is f_pop else 178)), st['pop'], font=pf, fill=WHITE if col == RED else NAVY)
    if st.get('banner'):
        txt = 'PLACED   14.0 s   0 hits   100 points'
        bw = d.textlength(txt, font=f_ban) + 80
        bx = (1920 - bw) / 2 - 140
        rr(d, (bx, 880, bx + bw, 952), 16, NAVY + (236,))
        d.rectangle((bx, 880, bx + 8, 952), fill=GREEN)
        d.text((bx + 40, 890), txt, font=f_ban, fill=WHITE)
    return Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')


ENC = ['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
# 14-slide deck (owner, 2026-11-02: fewer slides): world runs into the CAD board, pro runs into the placed beam.
CUTS = {'hook': (0, 12), 'world': (12, 28), 'practice': (28, 40), 'pro': (40, 64), 'wind': (64, 72)}
STILL_AT = {'hook': 4.0, 'world': 16.0, 'practice': 34.0, 'pro': 49.0, 'wind': 66.0}


def side_by_side():
    bg = Image.new('RGB', (1920, 1080), NAVY)
    d = ImageDraw.Draw(bg)
    big = F('b', 56)
    t = 'The same lift, 3 times'
    d.text(((1920 - d.textlength(t, font=big)) / 2, 150), t, font=big, fill=WHITE)
    bg.paste(LOGO.resize((int(LOGO.width * 60 / LOGO.height), 60)), (64, 64), LOGO.resize((int(LOGO.width * 60 / LOGO.height), 60)))
    for i, (lab, col) in enumerate([('FIRST TRY', RED), ('PRACTICE', YEL), ('AFTER PRACTICE', GREEN)]):
        x = 24 + i * 632
        tw = d.textlength(lab, font=f_pop)
        rr(d, (x + 312 - tw / 2 - 22, 300, x + 312 + tw / 2 + 22, 362), 28, col)
        d.text((x + 312 - tw / 2, 304), lab, font=f_pop, fill=WHITE if col == RED else NAVY)
    bg.save(HERE / 'work' / 'sbs_bg.png')
    seq = str(OUT_FR / 'o%04d.jpg')
    fc = ('[1:v]trim=start_frame=0:end_frame=360,setpts=PTS-STARTPTS,scale=624:351[a];'
          '[2:v]trim=start_frame=840:end_frame=1200,setpts=PTS-STARTPTS,scale=624:351[b];'
          '[3:v]trim=start_frame=1200:end_frame=1740,setpts=(PTS-STARTPTS)/1.5,scale=624:351[c];'
          '[0:v][a]overlay=24:400:shortest=1[x];[x][b]overlay=656:400[y];[y][c]overlay=1288:400,fps=30[v]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', '30', '-t', '12', '-i', str(HERE / 'work' / 'sbs_bg.png')]
                   + sum([['-framerate', '30', '-i', seq] for _ in range(3)], [])
                   + ['-filter_complex', fc, '-map', '[v]', '-t', '12'] + ENC + [str(CLIPS / 'sidebyside.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '10', '-i', str(CLIPS / 'sidebyside.mp4'), '-frames:v', '1',
                    '-c:v', 'libwebp', '-quality', '80', str(STILLS / 'sidebyside.webp')], check=True)


def main():
    OUT_FR.mkdir(exist_ok=True)
    frames = sorted(FR.glob('f*.jpg'))
    print(len(frames), 'frames')
    for i, p in enumerate(frames):
        draw(Image.open(p), i / FPS).save(OUT_FR / f'o{i:04d}.jpg', quality=94)
    CLIPS.mkdir(parents=True, exist_ok=True)
    n = len(frames)
    for name, (a, b) in CUTS.items():
        a, b = a * FPS, min(b * FPS, n)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(a), '-i', str(OUT_FR / 'o%04d.jpg'),
                        '-frames:v', str(b - a)] + ENC + [str(CLIPS / f'{name}.mp4')], check=True)
        i = min(n - 1, round(STILL_AT[name] * FPS))
        Image.open(OUT_FR / f'o{i:04d}.jpg').save(STILLS / f'{name}.webp', quality=80)
    side_by_side()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(OUT_FR / 'o%04d.jpg')] + ENC
                   + [str(VID / 'demo-preview.mp4')], check=True)
    print('clips:', sorted(p.name for p in CLIPS.glob('*.mp4')))


if __name__ == '__main__':
    main()
