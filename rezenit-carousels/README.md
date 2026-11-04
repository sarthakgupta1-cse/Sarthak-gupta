# RezenIt daily carousels

Five 6-slide carousels per day (1080×1350, 4:5) about quitting p*rn, ending in a RezenIt app CTA.

```
assets/            app.jpg (app screenshot), logo-t.png / mark-t.png (transparent logo)
content/           <YYYY-MM-DD>.json (slide copy) + <YYYY-MM-DD>-captions.md
carousels/         rendered output: "<DD-MM-YY> Carousel <n>/<1..6>.png"
render.js          content JSON -> PNG slides (Playwright)
```

## Brand facts (from rezenit.com — use these, don't invent features)
- Positioning: "Break the loop. Build a life that does not need the escape." For people tired of white-knuckling it alone.
  Shame-free, private by design, science-informed tools, real support when urges hit.
- Features: 1-on-1 accountability (matched with real people), p*rn blocker, streak tracking, step-by-step recovery
  program (guided audio sessions + daily actions), anonymous community, public habit tracking (partner sees progress),
  panic button (instant tools to stop urges), AI therapist & coach, daily journaling, "Learn the truth" guides.
- Stores: App Store and Google Play. Site CTA: "One download. A steadier week starts tomorrow."
- RezenIt is a self-help tool, not a substitute for professional care: never make medical promises.
- CTA slides: set `features` to 3 short chips matching the carousel's topic.

## Make a new day

1. Copy the latest `content/*.json`, set `"date"` to `DD-MM-YY`, write 5 new carousels.
   Each carousel: one `theme` (single background color `bg` + accents `a1`/`a2`) and exactly 6 slides.
   Slide types: `hook`, `point`, `chain`, `list`, `cta` (always last). `[[text]]` = gradient highlight,
   `<b>` = bold, `\n` = line break. Write "p*rn", never the full word.
2. `node render.js content/<date>.json carousels`
3. Check the console for `WARN overflow`, review the PNGs, write the captions file.
4. Upload the five `carousels/<DD-MM-YY> Carousel N` folders into the Drive folder
   "Rezenit TikTok Carousel" (drag the folders into Drive in the browser).

## Topics already used
- 04-11-26: No Nut November Day 7 · 7 signs · 90-day timeline · 1 AM relapse playbook · softcore trap
