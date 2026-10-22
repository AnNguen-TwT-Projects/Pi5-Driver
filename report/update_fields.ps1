# Mở báo cáo bằng Word, cập nhật mục lục / danh mục hình, bảng / số trang,
# lưu lại .docx và xuất thêm bản PDF để kiểm tra.
$ErrorActionPreference = 'Stop'
$docx = Join-Path $PSScriptRoot 'Report_LCD2004_Pi5_v2.docx'
$pdf  = Join-Path $PSScriptRoot 'Report_LCD2004_Pi5_v2.pdf'
$log  = Join-Path $PSScriptRoot 'update_fields.log'

function Step($msg) { "$(Get-Date -Format HH:mm:ss) $msg" | Add-Content -Path $log -Encoding utf8 }

Set-Content -Path $log -Value '' -Encoding utf8
$word = New-Object -ComObject Word.Application
Step 'word started'
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($docx, $false, $false, $false)
    Step 'opened'
    # Cập nhật 2 lần: lần 1 điền mục lục, lần 2 sửa số trang sau khi mục lục dài ra
    for ($k = 0; $k -lt 2; $k++) {
        foreach ($t in $doc.TablesOfContents) { $t.Update() | Out-Null }
        Step "toc updated $k"
        foreach ($t in $doc.TablesOfFigures) { $t.Update() | Out-Null }
        Step "tof updated $k"
    }
    Step ("pages: " + $doc.ComputeStatistics(2))
    $doc.Save()
    Step 'saved'
    # Không xuất PDF bằng Word: trên máy này ExportAsFixedFormat bị treo.
    # Bản PDF xem trước lấy từ preview.sh (LibreOffice trong WSL).
    $doc.Close()
} finally {
    $word.Quit()
    Step 'quit'
}
