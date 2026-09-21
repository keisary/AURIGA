// Slide 1 -- Cover
// Page type: Cover (asymmetric left/right with constellation motif)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Decorative constellation dots (back layer)
  const stars = [
    { x: 0.45, y: 0.55, s: 0.06 },
    { x: 1.20, y: 0.30, s: 0.04 },
    { x: 1.85, y: 0.75, s: 0.05 },
    { x: 2.40, y: 0.40, s: 0.07 },
    { x: 7.10, y: 0.45, s: 0.05 },
    { x: 7.95, y: 0.85, s: 0.06 },
    { x: 8.70, y: 0.35, s: 0.04 },
    { x: 9.30, y: 0.95, s: 0.05 },
    { x: 0.80, y: 4.70, s: 0.04 },
    { x: 1.55, y: 5.05, s: 0.05 },
    { x: 2.20, y: 4.80, s: 0.06 },
    { x: 7.40, y: 4.85, s: 0.05 },
    { x: 8.20, y: 5.10, s: 0.07 },
    { x: 9.00, y: 4.65, s: 0.04 },
  ];
  stars.forEach((star) => {
    slide.addShape(pres.shapes.OVAL, {
      x: star.x, y: star.y, w: star.s, h: star.s,
      fill: { color: theme.accent, transparency: 30 },
      line: { type: 'none' },
    });
  });

  // Connecting lines (constellation strokes)
  const links = [
    [0.48, 0.58, 1.22, 0.32],
    [1.22, 0.32, 1.87, 0.77],
    [1.87, 0.77, 2.42, 0.42],
    [7.12, 0.47, 7.97, 0.87],
    [7.97, 0.87, 8.72, 0.37],
    [8.72, 0.37, 9.32, 0.97],
    [0.82, 4.72, 1.57, 5.07],
    [1.57, 5.07, 2.22, 4.82],
    [7.42, 4.87, 8.22, 5.12],
    [8.22, 5.12, 9.02, 4.67],
  ];
  links.forEach((l) => {
    slide.addShape(pres.shapes.LINE, {
      x: l[0], y: l[1], w: l[2] - l[0], h: l[3] - l[1],
      line: { color: theme.accent, width: 0.5, transparency: 60 },
    });
  });

  // Eyebrow / context
  slide.addText('ALPACA AI TRADING AGENTS HACKATHON 2026', {
    x: 0.6, y: 1.85, w: 8.8, h: 0.35,
    fontSize: 14, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0, align: 'left',
  });

  // Big title
  slide.addText('AURIGA', {
    x: 0.55, y: 2.20, w: 8.9, h: 1.20,
    fontSize: 96, fontFace: 'Cambria', color: theme.primary,
    bold: true, charSpacing: 8, margin: 0, align: 'left', fit: 'shrink',
  });

  // Subtitle
  slide.addText('Autonomous Quant Research & Investment Agent', {
    x: 0.6, y: 3.45, w: 8.8, h: 0.50,
    fontSize: 22, fontFace: 'Calibri', color: theme.primary,
    margin: 0, align: 'left',
  });

  // Tagline (italic accent)
  slide.addText('Discover, validate, deploy -- the LLM narrates, it never decides.', {
    x: 0.6, y: 4.05, w: 8.8, h: 0.40,
    fontSize: 16, fontFace: 'Calibri', color: theme.secondary,
    italic: true, margin: 0, align: 'left',
  });

  // Bottom meta
  slide.addShape(pres.shapes.LINE, {
    x: 0.6, y: 4.80, w: 1.5, h: 0,
    line: { color: theme.accent, width: 2 },
  });
  slide.addText('Submission deck  |  5-year backtest  |  Alpaca paper $100k', {
    x: 0.6, y: 4.90, w: 6.0, h: 0.30,
    fontSize: 12, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  slide.addText('github.com/keisary/AURIGA', {
    x: 6.5, y: 4.90, w: 3.0, h: 0.30,
    fontSize: 12, fontFace: 'Calibri', color: theme.accent,
    margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
