# RezenIt daily carousels

Five 6-slide carousels per day (1080×1350, 4:5) about quitting p*rn, ending in a RezenIt app CTA.

```
assets/            app.jpg (app screenshot), logo-t.png / mark-t.png (transparent logo)
content/           <YYYY-MM-DD>.json (slide copy) + <YYYY-MM-DD>-captions.md
carousels/         rendered output: "<DD-MM-YY> Carousel <n>/<1..6>.png"
render.js          content JSON -> PNG slides (Playwright)
```

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
