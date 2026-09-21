// Slide 6 -- Why AURIGA is Defensible
// Page type: Content / Text (4 numbered points)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Title block
  slide.addText('04  /  WHY AURIGA IS DEFENSIBLE', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('Four things that are hard to copy', {
    x: 0.5, y: 0.60, w: 9, h: 0.55,
    fontSize: 28, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0,
  });

  // 4 numbered rows
  const points = [
    {
      n: '01',
      title: 'Explainable alpha',
      body: 'Every position traces to a human-readable rule with backtested metrics. Not a black box -- you can read why AURIGA is in a trade.',
    },
    {
      n: '02',
      title: 'Honest research',
      body: 'We measured what does NOT work (long volatility: median Sharpe -2.6) and re-purposed A2 as a risk signal. The system adapts to evidence, not vibes.',
    },
    {
      n: '03',
      title: 'Two orthogonal income streams',
      body: 'Directional debit spreads (trend, A1) + gated premium selling (range / theta, A3) -- one hedges the other in most regimes.',
    },
    {
      n: '04',
      title: 'Institutional-grade risk',
      body: '8 deterministic gates + ML risk flags before any order. Fail-closed by design: any gate that cannot be verified blocks the order.',
    },
  ];

  const rowH = 0.85;
  const startY = 1.30;
  const gapY = 0.05;
  points.forEach((p, i) => {
    const y = startY + i * (rowH + gapY);
    // Row card
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 8.85, h: rowH,
      fill: { color: theme.light },
      line: { color: theme.accent, width: 0.5, transparency: 60 },
      rectRadius: 0.06,
    });
    // Number badge
    slide.addText(p.n, {
      x: 0.65, y: y + 0.05, w: 0.85, h: rowH - 0.10,
      fontSize: 40, fontFace: 'Cambria', color: theme.accent,
      bold: true, margin: 0, align: 'center', valign: 'middle',
    });
    // Title
    slide.addText(p.title, {
      x: 1.65, y: y + 0.10, w: 7.55, h: 0.30,
      fontSize: 16, fontFace: 'Cambria', color: theme.primary,
      bold: true, margin: 0,
    });
    // Body
    slide.addText(p.body, {
      x: 1.65, y: y + 0.40, w: 7.55, h: rowH - 0.45,
      fontSize: 12, fontFace: 'Calibri', color: theme.primary,
      margin: 0,
    });
  });

  // Footer + page number
  slide.addText('AURIGA  |  Defensible', {
    x: 0.5, y: 5.20, w: 6.0, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  slide.addText('06', {
    x: 9.3, y: 5.20, w: 0.5, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
