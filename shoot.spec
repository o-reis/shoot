# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=['.', 'src/network/generated'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('src/network/generated', 'src/network/generated'),
    ],
    hiddenimports=[
        'grpc',
        'grpc._cython.cygrpc',
        'game_pb2',
        'game_pb2_grpc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='shoot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)
