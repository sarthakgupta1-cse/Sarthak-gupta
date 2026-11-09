# RezenIt daily carousels

15 carousels per day (5 each for Shalini, Tanmay and Yash), 6 slides each, (1080×1350, 4:5) about quitting p*rn, ending in a RezenIt app CTA.

```
assets/            app.jpg (app screenshot), logo-t.png / mark-t.png (transparent logo)
content/           <YYYY-MM-DD>.json (slide copy) + <YYYY-MM-DD>-captions.md
carousels/         rendered output: "<Person>/<DD-MM-YY> Carousel <n>/<1..6>.png" + manifest.json
                   (Person = Shalini, Tanmay, Yash; days before 06-11 sit at the top level)
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

## Backgrounds per person (each posts from a different account — keep them distinct)
- **Shalini:** the brand navy/purple/plum darks, varied per carousel (e.g. #0C1633, #1A1036, #0B1A3A, #22102E, #0A1A30). No green or teal.
- **Tanmay:** black, `#050508`, on all 5 carousels. Accents can vary.
- **Yash:** deep emerald green, `#04241A`, on all 5 carousels. Accents: mint/cyan `a1` with blue or lavender `a2`.

## Copy rule: name it openly
Every carousel is about **p*rn addiction** and must say so — nobody should have to guess the topic.
- Slide 1 (hook) always contains "p*rn" or "p*rn addiction" ("P*rn" at the start of a sentence).
- At least 2 of slides 2–5 mention p*rn by name; don't hide behind "the habit", "it", "this" or "the screen".
- CTA and captions name it too ("quit p*rn", "p*rn addiction recovery").
- Never write the uncensored word. render.js prints `WARN` lines if any of these are broken — fix them before pushing.

## Make a new day

1. Write three files `content/<YYYY-MM-DD>-<shalini|tanmay|yash>.json`, each with `"date": "DD-MM-YY"`,
   `"owner": "Shalini"|"Tanmay"|"Yash"` and 5 carousels. All 15 topics must be different from each other and from every earlier day.
   Each carousel: one `theme` (single background color `bg` + accents `a1`/`a2`) and exactly 6 slides.
   Slide types: `hook`, `point`, `chain`, `list`, `cta` (always last). `[[text]]` = gradient highlight,
   `<b>` = bold, `\n` = line break. Write "p*rn", never the full word.
2. Remove previous days' image folders first (`git rm -r carousels/*/<old date> Carousel *`); the content JSON
   and captions stay as the record. Then `node render.js content/<file>.json carousels` for each of the three
   files (also rebuilds manifest.json; `node render.js --manifest carousels` rebuilds it alone).
3. Check the console for `WARN overflow`, review the PNGs, write the captions file.
4. Commit and push to `claude/brave-davinci-pbopjl`. The Google Apps Script in `drive-sync/Code.gs`
   (running in the owner's Google account) copies new folders into the Drive folder
   "Rezenit TikTok Carousel" every hour. Yesterday's folders stay until 11 AM IST, then go to the Drive Trash.
   Nothing to upload or delete by hand.

## Topics already used
- 04-11-26: No Nut November Day 7 · 7 signs · 90-day timeline · 1 AM relapse playbook · softcore trap
- 05-11-26: 5 relapse excuses · performance issues at 24 · room/environment design · accountability · 6 benefits of quitting
- 06-11-26: Relapse binge after a slip · HALT (hungry/angry/lonely/tired) · replacement addiction (doomscrolling) · secrecy vs trust in relationships · Day 31 after No Nut November
- 06-11-26 Shalini: urge surfing · boredom trigger · weekends · signs you're healing after a relapse · streak-counter obsession
- 06-11-26 Tanmay: morning routine · confidence & comparison · 4 lies about real relationships · dating while quitting · workout as urge-killer
- 06-11-26 Yash: exam/deadline stress · 3 nightly journaling questions · advice to my 15-year-old self · 4 myths · identity shift ("I don't do that")
- 07-11-26 Shalini: overconfidence / day-5 wave · flatline vs depression (when to get help) · self-compassion vs shame · isolation & building connection · working from home alone
- 07-11-26 Tanmay: extinction burst (urges louder before quieter) · hours p*rn costs per year · disciplined everywhere but here · mental replay / fantasies · therapy isn't weakness
- 07-11-26 Yash: 5 phone settings · 3-second rule for surprise triggers · your "why" · learn a skill for the rest of November · helping a friend who's struggling
- 08-11-26 Shalini: 3 p*rn habits linked to addiction (binge, tab-jumping, tolerance) · relapse starts days before · coming-home trigger · is p*rn addiction real (ICD-11) · p*rn for anxiety relief
- 08-11-26 Tanmay: wanting vs enjoying p*rn · p*rn & sleep loop · telling your partner · p*rn addiction at 30+ · 5-step starter kit
- 08-11-26 Yash: side doors (Reddit, games, anime, image search) · money spent on p*rn · p*rn & procrastination · 5 questions before you open p*rn · incognito/hiding rituals
- 09-11-26 Shalini: 4 CBT tools for p*rn addiction · partner's self-esteem · Sunday-night relapse · why we need to talk about p*rn addiction · a good p*rn-free day routine
- 09-11-26 Tanmay: "dopamine reset" myths · 4 needs p*rn fills · group chats sending p*rn · 4 p*rn blocker loopholes · map your p*rn triggers
- 09-11-26 Yash: breakups & p*rn relapse · travel/hotel rooms · moderation vs quitting · new city loneliness · craving p*rn after a big win
