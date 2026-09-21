// Slide 5 -- Alpaca Infrastructure
// Page type: Content / Mixed (3 vertical sections)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Title block
  slide.addText('03  /  ALPACA INFRASTRUCTURE', {
    x: 0.5, y: 0.30, w: 9, h: 0.30,
    fontSize: 11, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 4, margin: 0,
  });
  slide.addText('Built on Alpaca paper. Real market data. Atomic option spreads.', {
    x: 0.5, y: 0.60, w: 9, h: 0.55,
    fontSize: 26, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0, fit: 'shrink',
  });

  // 3 vertical sections
  const sections = [
    {
      x: 0.50,
      tag: 'MARKET DATA',
      title: 'IEX feed + option chains',
      points: [
        '5 years of 1H / 1D bars',
        'Live option chains (OCC symbols)',
        'Universe: 25 US large caps + ETFs',
        '36 features (technical + quantitative)',
      ],
    },
    {
      x: 3.65,
      tag: 'EXECUTION',
      title: 'MLEG multi-leg orders',
      points: [
        'alpaca-py + multi-leg Level 3',
        'Vertical spreads as atomic orders',
        'Zero commissions on paper',
        'Bracket TP/SL + buying-power checks',
      ],
    },
    {
      x: 6.80,
      tag: 'CADENCE',
      title: 'Research -> signal -> risk',
      points: [
        'Research cycle (A1 + A2 + A3)',
        'Current-signal check + spread picker',
        'Risk gates -> paper orders',
        'Daily LLM narrative + Streamlit',
      ],
    },
  ];

  sections.forEach((s) => {
    // Card
    slide.addShape(pres.shapes.RECTANGLE, {
      x: s.x, y: 1.35, w: 2.85, h: 3.55,
      fill: { color: theme.light },
      line: { color: theme.accent, width: 0.5, transparency: 60 },
      rectRadius: 0.10,
    });
    // Accent strip
    slide.addShape(pres.shapes.RECTANGLE, {
      x: s.x, y: 1.35, w: 0.10, h: 3.55,
      fill: { color: theme.accent },
      line: { type: 'none' },
    });
    // Tag
    slide.addText(s.tag, {
      x: s.x + 0.30, y: 1.50, w: 2.50, h: 0.30,
      fontSize: 11, fontFace: 'Calibri', color: theme.accent,
      bold: true, charSpacing: 3, margin: 0,
    });
    // Title
    slide.addText(s.title, {
      x: s.x + 0.30, y: 1.82, w: 2.50, h: 0.50,
      fontSize: 18, fontFace: 'Cambria', color: theme.primary,
      bold: true, margin: 0, fit: 'shrink',
    });
    // Bullet list
    const bullets = s.points.map((p, i) => ({
      text: p,
      options: { bullet: { code: '25A0' }, breakLine: i < s.points.length - 1 },
    }));
    slide.addText(bullets, {
      x: s.x + 0.30, y: 2.45, w: 2.50, h: 2.30,
      fontSize: 12, fontFace: 'Calibri', color: theme.primary,
      paraSpaceAfter: 6, margin: 0,
    });
  });

  // Bottom mini-flow
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.50, y: 5.00, w: 8.85, h: 0.30,
    fill: { color: theme.bg },
    line: { color: theme.accent, width: 0.5, transparency: 50 },
    rectRadius: 0.04,
  });
  slide.addText('ING  ->  FEAT  ->  DISC  ->  VAL  ->  SEL  ->  OPT  ->  RSK  ->  EXEC  ->  NAR', {
    x: 0.50, y: 5.00, w: 8.85, h: 0.30,
    fontSize: 10, fontFace: 'Calibri', color: theme.accent,
    bold: true, charSpacing: 2, margin: 0, align: 'center', valign: 'middle',
  });

  // Footer + page number
  slide.addText('AURIGA  |  Alpaca infrastructure', {
    x: 0.5, y: 5.40, w: 6.0, h: 0.20,
    fontSize: 9, fontFace: 'Calibri', color: theme.secondary,
    margin: 0, align: 'left',
  });
  slide.addText('05', {
    x: 9.3, y: 5.40, w: 0.5, h: 0.20,
    fontSize: 9, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
