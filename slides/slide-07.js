// Slide 7 -- Limitations (stated honestly)
// Page type: Content / Text (3 limit blocks)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Title block
  slide.addText('05  /  LIMITATIONS', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('Stated honestly -- not marketing', {
    x: 0.5, y: 0.60, w: 9, h: 0.55,
    fontSize: 28, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0,
  });

  // 3 limit blocks (vertical stack)
  const limits = [
    {
      tag: 'L1',
      title: 'Options backtest is a synthetic proxy',
      body: 'Alpaca free tier has no historical option prices. Option P&L in backtests is estimated via Black-Scholes repricing (IV = RV + risk premium). Live paper fills (real option quotes) are the ground truth.',
    },
    {
      tag: 'L2',
      title: 'A final 20% temporal holdout is kept untouched',
      body: 'During strategy discovery and admission, we keep a virgin 20% tail of the data. Metrics shown are from train + validation; holdout results are not claimed yet.',
    },
    {
      tag: 'L3',
      title: '5 days of P&L is a small sample',
      body: 'Results during the competition period are indicative, not statistically conclusive. Paper trading research -- not investment advice.',
    },
  ];

  const blockH = 1.05;
  const startY = 1.40;
  const gapY = 0.10;
  limits.forEach((l, i) => {
    const y = startY + i * (blockH + gapY);
    // Card
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 8.85, h: blockH,
      fill: { color: theme.light },
      line: { color: 'FF6B6B', width: 0.75, transparency: 50 },
      rectRadius: 0.08,
    });
    // Tag
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.65, y: y + 0.20, w: 0.65, h: 0.65,
      fill: { color: 'FF6B6B' },
      line: { type: 'none' },
      rectRadius: 0.06,
    });
    slide.addText(l.tag, {
      x: 0.65, y: y + 0.20, w: 0.65, h: 0.65,
      fontSize: 18, fontFace: 'Cambria', color: theme.bg,
      bold: true, margin: 0, align: 'center', valign: 'middle',
    });
    // Title
    slide.addText(l.title, {
      x: 1.45, y: y + 0.15, w: 7.75, h: 0.35,
      fontSize: 16, fontFace: 'Cambria', color: theme.primary,
      bold: true, margin: 0,
    });
    // Body
    slide.addText(l.body, {
      x: 1.45, y: y + 0.50, w: 7.75, h: blockH - 0.55,
      fontSize: 12, fontFace: 'Calibri', color: theme.primary,
      margin: 0,
    });
  });

  // Disclaimer at bottom
  slide.addText('Paper trading research only -- not investment advice.', {
    x: 0.5, y: 4.95, w: 8.85, h: 0.25,
    fontSize: 11, fontFace: 'Calibri', color: theme.secondary,
    italic: true, margin: 0, align: 'center',
  });

  // Footer + page number
  slide.addText('AURIGA  |  Limitations', {
    x: 0.5, y: 5.30, w: 6.0, h: 0.25,
    fontSize: 9, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  slide.addText('07', {
    x: 9.3, y: 5.30, w: 0.5, h: 0.25,
    fontSize: 9, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
