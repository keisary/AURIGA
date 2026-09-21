// Slide 3 -- AI Logic (3 Agents)
// Page type: Content / Comparison cards (3 cards side by side)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Title block
  slide.addText('01  /  AI LOGIC', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('Three agents, three testable theses', {
    x: 0.5, y: 0.60, w: 9, h: 0.55,
    fontSize: 28, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0,
  });

  // Three cards
  const cards = [
    {
      x: 0.50,
      tag: 'A1  DIRECTION',
      title: 'Directional alpha',
      method: 'XGBoost -> explainable rules',
      expr: 'Debit vertical spreads (bull / bear)',
      kpi: '9',
      kpiLbl: 'rules admitted',
      note: 'Sharpe >= 2, WR >= 0.65, PF >= 1.5, >= 30 trades, BH/FDR-controlled',
      colorTag: theme.accent,
    },
    {
      x: 3.65,
      tag: 'A2  VOLATILITY RISK',
      title: 'Volatility risk signal',
      method: 'XGBoost classifier on vol shock',
      expr: 'No execution -- a guard for the risk engine',
      kpi: '~0.75',
      kpiLbl: 'AUC on RV[t+24] > 1.5x RV[t]',
      note: 'Long-vol straddles measured at median Sharpe -2.6. Buying vol loses -- so A2 stops premium sales when it flags danger.',
      colorTag: 'FF6B6B',
    },
    {
      x: 6.80,
      tag: 'A3  PREMIUM SELLER',
      title: 'Gated income engine',
      method: 'AVOID_SELL rules on the ~2% tail',
      expr: 'Put / call credit spreads (~3% OTM, 5% wide)',
      kpi: '~98%',
      kpiLbl: 'of periods structurally profitable',
      note: 'Stops selling when overbought + drawdown + regime shift coincide -- exactly the rare tail ML can flag.',
      colorTag: theme.accent,
    },
  ];

  cards.forEach((c) => {
    // Card background
    slide.addShape(pres.shapes.RECTANGLE, {
      x: c.x, y: 1.30, w: 2.85, h: 3.65,
      fill: { color: theme.light },
      line: { color: c.colorTag, width: 0.75, transparency: 50 },
      rectRadius: 0.10,
    });
    // Accent bar
    slide.addShape(pres.shapes.RECTANGLE, {
      x: c.x, y: 1.30, w: 2.85, h: 0.10,
      fill: { color: c.colorTag },
      line: { type: 'none' },
    });
    // Tag
    slide.addText(c.tag, {
      x: c.x + 0.20, y: 1.50, w: 2.50, h: 0.30,
      fontSize: 11, fontFace: 'Calibri', color: c.colorTag,
      bold: true, charSpacing: 3, margin: 0,
    });
    // Title
    slide.addText(c.title, {
      x: c.x + 0.20, y: 1.82, w: 2.50, h: 0.45,
      fontSize: 18, fontFace: 'Cambria', color: theme.primary,
      bold: true, margin: 0, fit: 'shrink',
    });
    // Method
    slide.addText(c.method, {
      x: c.x + 0.20, y: 2.30, w: 2.50, h: 0.30,
      fontSize: 12, fontFace: 'Calibri', color: theme.primary,
      margin: 0,
    });
    // Expression
    slide.addText(c.expr, {
      x: c.x + 0.20, y: 2.60, w: 2.50, h: 0.35,
      fontSize: 11, fontFace: 'Calibri', color: theme.secondary,
      italic: true, margin: 0,
    });
    // KPI
    slide.addText(c.kpi, {
      x: c.x + 0.20, y: 3.05, w: 2.50, h: 0.65,
      fontSize: 40, fontFace: 'Cambria', color: c.colorTag,
      bold: true, margin: 0, fit: 'shrink',
    });
    slide.addText(c.kpiLbl, {
      x: c.x + 0.20, y: 3.70, w: 2.50, h: 0.30,
      fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
      margin: 0,
    });
    // Note
    slide.addText(c.note, {
      x: c.x + 0.20, y: 4.05, w: 2.50, h: 0.85,
      fontSize: 10, fontFace: 'Calibri', color: theme.primary,
      margin: 0,
    });
  });

  // Footer
  slide.addText('AURIGA  |  AI logic', {
    x: 0.5, y: 5.10, w: 6.0, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  // Page number
  slide.addText('03', {
    x: 9.3, y: 5.10, w: 0.5, h: 0.25,
    fontSize: 10, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
