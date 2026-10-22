#!/bin/bash
# Vẽ lại các sơ đồ: chạy trong WSL từ thư mục này
cd "$(dirname "$0")"
for f in *.dot; do
    dot -Tpng -Gdpi=200 "$f" -o "${f%.dot}.png" || echo "FAIL $f"
done
ls -la *.png
