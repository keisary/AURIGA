// Slide 8 -- Closing
// Page type: Summary / Closing (slogan + contact)
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  // Decorative constellation at top
  const stars = [
    { x: 0.5, y: 0.4, s: 0.05 },
    { x: 1.4, y: 0.7, s: 0.07 },
    { x: 2.3, y: 0.4, s: 0.05 },
    { x: 7.5, y: 0.5, s: 0.06 },
    { x: 8.4, y: 0.8, s: 0.05 },
    { x: 9.2, y: 0.4, s: 0.05 },
  ];
  stars.forEach((star) => {
    slide.addShape(pres.shapes.OVAL, {
      x: star.x, y: star.y, w: star.s, h: star.s,
      fill: { color: theme.accent, transparency: 30 },
      line: { type: 'none' },
    });
  });
  // Lines
  const links = [
    [0.52, 0.42, 1.42, 0.72],
    [1.42, 0.72, 2.32, 0.42],
    [7.52, 0.52, 8.42, 0.82],
    [8.42, 0.82, 9.22, 0.42],
  ];
  links.forEach((l) => {
    slide.addShape(pres.shapes.LINE, {
      x: l[0], y: l[1], w: l[2] - l[0], h: l[3] - l[1],
      line: { color: theme.accent, width: 0.5, transparency: 60 },
    });
  });

  // Big closing slogan
  slide.addText('"AURIGA doesn\'t ask an LLM whether to trade."', {
    x: 0.5, y: 1.50, w: 9, h: 0.80,
    fontSize: 30, fontFace: 'Cambria', color: theme.primary,
    bold: true, margin: 0, align: 'center', fit: 'shrink',
  });
  slide.addText('The quantitative system decides. The LLM explains.', {
    x: 0.5, y: 2.35, w: 9, h: 0.55,
    fontSize: 22, fontFace: 'Calibri', color: theme.accent,
    italic: true, margin: 0, align: 'center',
  });

  // Accent divider
  slide.addShape(pres.shapes.LINE, {
    x: 4.0, y: 3.10, w: 2.0, h: 0,
    line: { color: theme.accent, width: 2 },
  });

  // Three pillars
  const pillars = [
    { x: 0.5,  label: 'EXPLAINABLE',  sub: 'Every rule is human-readable' },
    { x: 3.65, label: 'DETERMINISTIC', sub: 'Risk gates before any order' },
    { x: 6.80, label: 'EVIDENCE-DRIVEN', sub: 'Measures what does not work' },
  ];
  pillars.forEach((p) => {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: p.x, y: 3.40, w: 2.85, h: 0.95,
      fill: { color: theme.light },
      line: { color: theme.accent, width: 0.5, transparency: 60 },
      rectRadius: 0.06,
    });
    slide.addText(p.label, {
      x: p.x + 0.15, y: 3.50, w: 2.55, h: 0.35,
      fontSize: 14, fontFace: 'Cambria', color: theme.accent,
      bold: true, charSpacing: 2, margin: 0, align: 'center',
    });
    slide.addText(p.sub, {
      x: p.x + 0.15, y: 3.85, w: 2.55, h: 0.40,
      fontSize: 11, fontFace: 'Calibri', color: theme.primary,
      margin: 0, align: 'center',
    });
  });

  // Repo + closing
  slide.addText('Repo  -->  github.com/keisary/AURIGA', {
    x: 0.5, y: 4.55, w: 9, h: 0.35,
    fontSize: 16, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'center',
  });
  slide.addText('Thanks  --  looking forward to the jury\'s questions.', {
    x: 0.5, y: 4.95, w: 9, h: 0.30,
    fontSize: 13, fontFace: 'Calibri', color: theme.secondary,
    italic: true, margin: 0, align: 'center',
  });

  // Page number
  slide.addText('08', {
    x: 9.3, y: 5.30, w: 0.5, h: 0.25,
    fontSize: 9, fontFace: 'Calibri', color: theme.accent,
    bold: true, margin: 0, align: 'right',
  });
}

module.exports = { createSlide };
