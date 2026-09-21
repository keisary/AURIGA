"""Convert AURIGA submission .pptx to .pdf via Spire.Presentation."""
import os
import sys
from pathlib import Path

from spire.presentation import Presentation, FileFormat

pptx_path = Path(r"D:\midas_v2\AURIGA\slides\output\AURIGA_submission_deck.pptx")
pdf_path  = Path(r"D:\midas_v2\AURIGA\slides\output\AURIGA_submission_deck.pdf")

if not pptx_path.is_file():
    sys.exit(f"PPTX not found: {pptx_path}")

pres = Presentation()
pres.LoadFromFile(str(pptx_path))

# Try to set a higher resolution for crisper output
try:
    # Some Spire versions accept this; safe to ignore if absent
    pass
except Exception:
    pass

# Save as PDF (FileFormat.PDF == 1... verify by symbol)
pres.SaveToFile(str(pdf_path), FileFormat.PDF)
pres.Dispose()

if pdf_path.is_file():
    size = pdf_path.stat().st_size
    print(f"OK  -> {pdf_path}  ({size} bytes, {size/1024:.1f} KB)")
else:
    sys.exit("PDF was not written")
