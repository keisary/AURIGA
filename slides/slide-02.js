// Slide 2 -- The Pitch
// Page type: Content / Text + flow diagram
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Eyebrow + title
  slide.addText('THE PITCH', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('Rules over vibes. The quant system decides. The LLM explains.', {
    x: 0.5, y: 0.60, w: 9, h: 0.60,
    fontSize: 28, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0, fit: 'shrink',
  });

  // Flow diagram: 4 boxes
  const flowY = 1.55;
  const flowH = 0.85;
  const boxes = [
    { x: 0.5,  w: 1.85, label: 'MARKET DATA', sub: '5y · 1H/1D · options' },
    { x: 2.85, w: 1.85, label: 'ML ENGINES',  sub: 'A1 + A2 + A3 · XGBoost' },
    { x: 5.20, w: 1.85, label: 'RISK ENGINE', sub: '8 gates · fail-closed' },
    { x: 7.55, w: 1.85, label: 'ALPACA MLEG', sub: 'paper · atomic multi-leg' },
  ];
  boxes.forEach((b, i) => {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: b.x, y: flowY, w: b.w, h: flowH,
      fill: { color: theme.light },
      line: { color: theme.accent, width: 0.75, transparency: 50 },
      rectRadius: 0.08,
    });
    slide.addText(b.label, {
      x: b.x + 0.10, y: flowY + 0.10, w: b.w - 0.20, h: 0.35,
      fontSize: 13, fontFace: 'Calibri', color: theme.accent,
      bold: true, charSpacing: 2, margin: 0, align: 'center',
    });
    slide.addText(b.sub, {
      x: b.x + 0.10, y: flowY + 0.45, w: b.w - 0.20, h: 0.35,
      fontSize: 11, fontFace: 'Calibri', color: theme.primary,
      margin: 0, align: 'center',
    });
    // Arrow between boxes
    if (i < boxes.length - 1) {
      const arrX = b.x + b.w + 0.08;
      slide.addShape(pres.shapes.RIGHT_TRIANGLE, {
        x: arrX, y: flowY + 0.32, w: 0.18, h: 0.20,
        fill: { color: theme.accent },
        line: { type: 'none' },
        rotate: 90,
      });
    }
  });

  // LLM strip below flow
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 2.65, w: 8.9, h: 0.45,
    fill: { color: theme.bg },
    line: { color: theme.accent, width: 1, dashType: 'dash', transparency: 30 },
    rectRadius: 0.05,
  });
  slide.addText('LLM  -->  narrates / interprets     (no execution authority)', {
    x: 0.5, y: 2.65, w: 8.9, h: 0.45,
    fontSize: 13, fontFace: 'Calibri', color: theme.secondary,
    italic: true, margin: 0, align: 'center', valign: 'middle',
  });

  // Stat callouts (4 KPIs)
  const stats = [
    { x: 0.50, label: '9',          sub: 'rules admitted' },
    { x: 2.80, label: '~0.75',      sub: 'vol shock AUC' },
    { x: 5.10, label: '8',          sub: 'risk gates' },
    { x: 7.40, label: '25',         sub: 'large-cap universe' },
  ];
  stats.forEach((s) => {
    slide.addText(s.label, {
      x: s.x, y: 3.40, w: 2.10, h: 0.85,
      fontSize: 60, fontFace: 'Cambria', color: theme.accent,
      bold: true, margin: 0, align: 'left', fit: 'shrink',
    });
    slide.addText(s.sub, {
      x: s.x, y: 4.30, w: 2.10, h: 0.30,
      fontSize: 12, fontFace: 'Calibri', color: theme.secondary,
      margin: 0, align: 'left',
    });
  });

  // Footer line
  slide.addText('AURIGA  |  Submission deck  |  Alpaca AI Trading Agents 2026', {
    x: 0.5, y: 5.10, w: 6.0, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  // Page number badge
  slide.addText('02', {
    x: 9.3, y: 5.10, w: 0.5, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
