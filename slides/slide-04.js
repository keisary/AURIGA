// Slide 4 -- Risk Engine (8 gates)
// Page type: Content / Data Viz (grid of gates)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Title block
  slide.addText('02  /  RISK ENGINE', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('8 deterministic gates -- fail-closed', {
    x: 0.5, y: 0.60, w: 9, h: 0.55,
    fontSize: 28, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0,
  });
  slide.addText('Every order passes ALL gates. If a gate cannot be verified, the order is blocked.', {
    x: 0.5, y: 1.18, w: 9, h: 0.30,
    fontSize: 13, fontFace: 'Calibri', color: theme.secondary,
    italic: true, margin: 0,
  });

  // 8 gates in a 4x2 grid
  const gates = [
    { code: 'G1', label: 'Daily loss limit',       rule: '-2% of equity  -->  no new orders' },
    { code: 'G2', label: 'Max exposure / asset',   rule: '10% of capital' },
    { code: 'G3', label: 'Max exposure / sector',  rule: '25% of capital' },
    { code: 'G4', label: 'Max total exposure',     rule: '80% of capital' },
    { code: 'G5', label: 'Max positions',          rule: '12 concurrent positions' },
    { code: 'G6', label: 'Vol danger (A2)',        rule: 'P(vol shock) > 0.35  -->  block premium sales' },
    { code: 'G7', label: 'AVOID_SELL (A3)',        rule: 'any triggered rule  -->  block premium sales' },
    { code: 'G8', label: 'Liquidation',            rule: 'total P&L < -25%  -->  close positions' },
  ];

  const colW = 2.10;
  const rowH = 1.30;
  const startX = 0.50;
  const startY = 1.65;
  const gapX = 0.15;
  const gapY = 0.15;

  gates.forEach((g, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = startX + col * (colW + gapX);
    const y = startY + row * (rowH + gapY);

    // Card
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w: colW, h: rowH,
      fill: { color: theme.light },
      line: { color: theme.accent, width: 0.5, transparency: 60 },
      rectRadius: 0.06,
    });
    // Code badge
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.50, h: 0.32,
      fill: { color: theme.accent },
      line: { type: 'none' },
      rectRadius: 0.04,
    });
    slide.addText(g.code, {
      x, y, w: 0.50, h: 0.32,
      fontSize: 12, fontFace: 'Cambria', color: theme.bg,
      bold: true, margin: 0, align: 'center', valign: 'middle',
    });
    // Label
    slide.addText(g.label, {
      x: x + 0.10, y: y + 0.40, w: colW - 0.20, h: 0.30,
      fontSize: 13, fontFace: 'Calibri', color: theme.primary,
      bold: true, margin: 0,
    });
    // Rule
    slide.addText(g.rule, {
      x: x + 0.10, y: y + 0.70, w: colW - 0.20, h: 0.55,
      fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
      margin: 0,
    });
  });

  // Bottom callout
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.50, y: 4.55, w: 8.85, h: 0.50,
    fill: { color: theme.bg },
    line: { color: theme.accent, width: 1 },
    rectRadius: 0.05,
  });
  slide.addText('LLM NEVER DECIDES  --  it only narrates facts after the deterministic engine has acted.', {
    x: 0.50, y: 4.55, w: 8.85, h: 0.50,
    fontSize: 13, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 2, margin: 0, align: 'center', valign: 'middle',
  });

  // Footer + page number
  slide.addText('AURIGA  |  Risk engine', {
    x: 0.5, y: 5.20, w: 6.0, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  slide.addText('04', {
    x: 9.3, y: 5.20, w: 0.5, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
