[app]
title = Aim Trainer
package.name = aimtrainer
package.domain = com.tgifernando
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = aim_trainer_android.py
version = 1.0

# Entry point
source.main = aim_trainer_android.py

requirements = python3,kivy==2.2.1,pillow

# Orientation: landscape works best for this game.
# Change to portrait or all if preferred.
orientation = landscape

fullscreen = 1

# Android settings
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# App icon — replace with your own 512x512 PNG to customize
# icon.filename = %(source.dir)s/icon.png

# Splash screen — replace with your own PNG to customize
# presplash.filename = %(source.dir)s/presplash.png
presplash_color = #0a0a19

[buildozer]
log_level = 2
warn_on_root = 1
