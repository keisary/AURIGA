// compile.js — assemble the AURIGA submission deck
const pptxgen = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.title = 'AURIGA - Submission Deck';
pres.author = 'AURIGA Team';
pres.company = 'Alpaca AI Trading Agents Hackathon 2026';

// Tech & Night palette mapped to 5-key theme (dark mode)
const theme = {
  primary:   'FFFFFF',   // body / title text on dark
  secondary: '8D99AE',   // muted secondary text
  accent:    'FFC300',   // gold star accent
  light:     '001D3D',   // card / panel background (slightly lighter than bg)
  bg:        '000814',   // slide background (deepest)
};

// Load slides 1..8 in order
for (let i = 1; i <= 8; i++) {
  const name = './slide-' + String(i).padStart(2, '0') + '.js';
  const mod = require(name);
  if (typeof mod.createSlide !== 'function') {
    throw new Error(name + ' does not export createSlide');
  }
  mod.createSlide(pres, theme);
}

const outDir = path.join(__dirname, 'output');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, 'AURIGA_submission_deck.pptx');

pres.writeFile({ fileName: outPath }).then(() => {
  console.log('Wrote: ' + outPath);
});
