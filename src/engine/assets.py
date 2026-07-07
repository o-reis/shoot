import os
import re
import sys

# sys._MEIPASS is set by PyInstaller when running from a bundled exe
_BASE = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(__file__), '..', '..'))
ASSETS_DIR = os.path.join(_BASE, 'assets')

_PIX_TO_SHADE = {
    '#': '█',
    '7': '▓',
    '*': '▒',
    'o': '▒',
    '.': '░',
    '+': '░',
    '0': '░',
    '5': '░',
    '~': ' ',
    ' ': ' ',
}


def char_to_shade(c):
    return _PIX_TO_SHADE.get(c, '░')


def _parse_tex_file(path):
    with open(path, encoding='utf-8') as f:
        src = f.read()

    src = re.sub(r"//.*", "", src)
    ns = {}
    for name, value in re.findall(r"\bvar\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\"([^\"]*)\"\s*;", src):
        ns[name] = value
    for name, value in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\+=\s*\"([^\"]*)\"\s*;", src):
        ns[name] = ns.get(name, "") + value
    return ns


def _build_tex(ns, varname, width, height, scale=2):
    raw = ns.get(varname, '')
    return {'texture': raw, 'width': width, 'height': height, 'scale': scale}


def sample_shaded(tex, sx, sy):
    if not tex or not tex.get('texture'):
        return '░'
    scale = tex.get('scale', 2)
    w = tex.get('width', 16)
    h = tex.get('height', 16)
    pixels = tex['texture']
    x = (scale * sx) % 1.0
    y = (scale * sy) % 1.0
    pos = int(h * y) * w + int(w * x)
    if pos < 0 or pos >= len(pixels):
        return '+'
    return char_to_shade(pixels[pos])


def sample_raw(tex, sx, sy):
    if not tex or not tex.get('texture'):
        return ' '
    scale = tex.get('scale', 2)
    w = tex.get('width', 16)
    h = tex.get('height', 16)
    pixels = tex['texture']
    x = (scale * sx) % 1.0
    y = (scale * sy) % 1.0
    pos = int(h * y) * w + int(w * x)
    if pos < 0 or pos >= len(pixels):
        return ' '
    return pixels[pos]


def _load_wall_textures(tns):
    return {
        '#': _build_tex(tns, 'cobblestone', 16, 16, scale=2),
        '$': _build_tex(tns, 'brick', 16, 16, scale=2),
        'U': _build_tex(tns, 'woodplanks', 16, 18, scale=4),
        'C': _build_tex(tns, 'textureC', 8, 8, scale=4),
        'T': _build_tex(tns, 'cobblestone', 16, 16, scale=2),
        'W': {
            'texture': 'DIRECTIONAL',
            'N': tns.get('textureN', ''),
            'S': tns.get('textureS', ''),
            'width': 16,
            'height': 16,
            'scale': 1,
        },
    }


def _load_sprite_defs(sns):
    def sp_tex(name, w, h):
        return {'texture': sns.get(name, ''), 'width': w, 'height': h, 'scale': 1}

    return {
        'P': {
            'width': 18, 'height': 25, 'aspect_ratio': 1.66, 'height_factor': 0.4,
            'angles': {
                'F': {**sp_tex('pogelfront', 18, 25),
                      'W1': sp_tex('pogelfrontW1', 18, 25),
                      'W2': sp_tex('pogelfrontW2', 18, 25)},
                'B': {**sp_tex('pogelback', 18, 25),
                      'W1': sp_tex('pogelbackW1', 18, 25),
                      'W2': sp_tex('pogelbackW2', 18, 25)},
                'L': {**sp_tex('pogelleft', 18, 25),
                      'W1': sp_tex('pogelleftW1', 18, 25),
                      'W2': sp_tex('pogelleftW2', 18, 25)},
                'R': {**sp_tex('pogelright', 18, 25),
                      'W1': sp_tex('pogelrightW1', 18, 25),
                      'W2': sp_tex('pogelrightW2', 18, 25)},
            },
        },
        'O': {
            'width': 16, 'height': 28, 'aspect_ratio': 1.46, 'height_factor': 0.7,
            'angles': {
                'F': {**sp_tex('obetrlF', 16, 28),
                      'W1': sp_tex('obetrlFW1', 16, 28),
                      'W2': sp_tex('obetrlFW2', 16, 28)},
                'B': {**sp_tex('obetrlB', 16, 28),
                      'W1': sp_tex('obetrlBW1', 16, 28),
                      'W2': sp_tex('obetrlBW2', 16, 28)},
                'L': {**sp_tex('obetrl', 16, 28),
                      'W1': sp_tex('obetrlW1', 16, 28),
                      'W2': sp_tex('obetrlW2', 16, 28)},
                'R': {**sp_tex('obetrlR', 16, 28),
                      'W1': sp_tex('obetrlRW1', 16, 28),
                      'W2': sp_tex('obetrlRW2', 16, 28)},
            },
        },
    }


def load_assets():
    tns = _parse_tex_file(os.path.join(ASSETS_DIR, 'textures.tex'))
    sns = _parse_tex_file(os.path.join(ASSETS_DIR, 'sprites.tex'))
    return _load_wall_textures(tns), _load_sprite_defs(sns)


try:
    WALL_TEX, SPRITE_DEFS = load_assets()
except Exception:
    WALL_TEX, SPRITE_DEFS = {}, {}
