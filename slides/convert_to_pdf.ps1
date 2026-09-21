$ErrorActionPreference = 'Stop'

$pptx = 'D:\midas_v2\AURIGA\slides\output\AURIGA_submission_deck.pptx'
$pdf  = 'D:\midas_v2\AURIGA\slides\output\AURIGA_submission_deck.pdf'

if (-not (Test-Path $pptx)) { throw "Input PPTX not found: $pptx" }

# PowerPoint COM automation
$ppt = New-Object -ComObject PowerPoint.Application
# Some PowerPoint installs forbid hiding; let it stay visible.

try {
    # Open with default args (untitled, readonly=False, untitled=False)
    $pres = $ppt.Presentations.Open($pptx)
    try {
        # ppSaveAsPDF = 32
        $pres.SaveAs($pdf, 32)
        Write-Output "Wrote: $pdf"
    } finally {
        $pres.Close()
    }
} finally {
    $ppt.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
}

# Verify
if (Test-Path $pdf) {
    $size = (Get-Item $pdf).Length
    Write-Output ("PDF size: {0} bytes ({1:N1} KB)" -f $size, ($size / 1024))
} else {
    throw "PDF was not created"
}
