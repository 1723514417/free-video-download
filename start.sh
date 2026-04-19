#!/bin/bash
export LC_ALL=zh_CN.UTF-8
export LANG=zh_CN.UTF-8
export LC_CTYPE=zh_CN.UTF-8
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

cd "$(dirname "$0")"
exec /e/aicode/free-video-download/venv/Scripts/python.exe /e/aicode/free-video-download/app.py