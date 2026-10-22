#!/bin/bash
# Xuất PDF bằng LibreOffice từ file .docx hiện có (chỉ để xem trước), ghép trang thành ảnh tổng.
# Tạo lại .docx: python3 make_report.py, rồi chạy update_fields.ps1 trên Windows.
cd "$(dirname "$0")"
mkdir -p preview && rm -f preview/*.jpg preview/*.pdf
soffice --headless --convert-to pdf --outdir preview Report_LCD2004_Pi5_v2.docx >/dev/null 2>&1
pdfinfo preview/Report_LCD2004_Pi5_v2.pdf | grep Pages
pdftoppm -jpeg -r 40 preview/Report_LCD2004_Pi5_v2.pdf preview/p
montage preview/p-*.jpg -tile 4x2 -geometry +4+4 -background "#888" preview/sheet.jpg
ls preview/sheet*.jpg
