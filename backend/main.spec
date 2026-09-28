# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../frontend/dist', 'frontend_dist'),  # bundled React UI
        ('assets/haarcascade_frontalface_default.xml', 'assets'),
    ],
    hiddenimports=[
        # Uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Project services
        'services.audio_processor',
        'services.transcription_service',
        'services.translation_service',
        'services.text_pipeline_service',
        'services.tts_service',
        'services.subtitle_service',
        'services.lip_sync_service',
        'services.math_phonetic_service',
        # ML / Whisper
        'whisper',
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'tqdm',
        # LangChain
        'langchain',
        'langchain_core',
        'langchain_openai',
        'langchain_core.messages',
        # TTS / Audio
        'edge_tts',
        'gtts',
        'pydub',
        'pydub.effects',
        'imageio_ffmpeg',
        # Translation
        'deep_translator',
        # Misc
        'requests',
        'dotenv',
        'multipart',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Math_AI_Dubber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='logo.ico',  # place logo.ico in backend/ to enable
)
