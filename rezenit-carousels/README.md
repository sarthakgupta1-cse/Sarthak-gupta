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

## NUMBER-LED FORMAT — the main format (user feedback 19-11-26, overrides everything below it)
The Reddit-thread style (16–19 Nov) did not perform and is retired — don't use composite stories, debate posts or
"what you're really looking for" essays as the default. Go back to the 10-11 style, and make EVERY carousel number-led:
- **Slide 1 starts with a number + a list word**, then frames the problem: "5 things…", "7 ways…", "6 facts…",
  "9 signs…", "4 mistakes…", "8 habits…", "3 reasons…", "10 lies…", "6 questions…", "5 rules…", "7 truths…",
  "4 stages…", "5 myths…", "6 triggers…". Vary the number and the list word across the 15.
- **Structure:** slide 1 = number hook naming the p*rn problem · slides 2–4 = the numbered points that explain
  (interpret) the problem · slide 5 = the solution / what to do (plus save/share or comment note) · slide 6 = CTA.
  For "facts"/"signs" lists the points are the problem and slide 5 gives the fix; for "ways"/"rules" lists slides
  2–4 can be the steps and slide 5 the "do this tonight" summary.
- Keep everything else from the content strategy: No Nut November framing (2+ per person through Nov 30), a real
  number from the stats bank per person, harsh/direct tone 1–2 per person, no promotion on slides 1–5, p*rn named.
- render.js warns "hook doesn't start with a number" — fix it.

## Content strategy (user feedback, 10-11-26) — follow on every run
**What performed best so far:** "7 signs p*rn is quietly running your life" (239 views, 2 saves) and
"What happens when you quit p*rn for 90 days" (202 views). Checklists/"signs" listicles and timelines win.
Make more in those formats, and better: "9 signs…", "Day 1 → Day 30 of No Nut November", "What p*rn does to
you in 1 week / 1 month / 1 year", "Signs your brain is healing", "The 5 stages of quitting p*rn".

1. **No Nut November (all of November):** at least 2 of each person's 5 carousels (6+ of 15) are framed around
   NNN — the day number ("Day 11 of NNN"), the mid-month wall, "you failed NNN, now what", "after NNN ends".
2. **Proven formats:** at least 2 per person are a signs/checklist listicle or a timeline.
3. **Not promotional:** slides 1–5 are 100% help for the community. No app, no features, no "RezenIt", no
   "panic button / in your app". Generic advice ("block p*rn", "tell a friend") is fine. The template already
   removes branding from slides 1–5. Slide 6 is 100% promotional (logo, name, app image, features, download).
4. **Real numbers:** at least 1 carousel per person uses a number from the stats bank below, with its source named
   on the slide. Never invent a stat; if you find a new one, add it to the bank with its source first.
5. **Bold and direct — very harsh is allowed:** drill-sergeant tone, call out excuses, lies and wasted time
   ("Stop lying to yourself." "You're not tired. You're avoiding your life."). Aim the harshness at the habit and the
   excuses, never at the person's worth — no "you're worthless/disgusting", nothing about self-harm. Mix 1–2 harsh
   carousels per person with supportive ones.
6. **Built to be saved and shared:** write things people want to keep (checklists, timelines, scripts, numbers)
   and send to a friend. The template adds "Save this" on slide 1, "Save for later" on 2–4 and "Send this to someone
   who's struggling" on slide 5; slide 5's note can also ask for a save/share instead of a comment.
7. CTA (slide 6) title must fit on 2 lines; render.js warns on overflow.

## Stats bank (verified — cite the source on the slide, keep the wording hedged)
- ~13% of web searches were for erotic content — analysis of ~400 million searches (Ogas & Gaddam, "A Billion Wicked Thoughts", 2011).
- P*rnhub alone had 42 billion visits in 2019 — about 115 million a day; average visit 10 min 28 sec (P*rnhub 2019 Year in Review).
- P*rnhub recorded 39 billion searches in 2019 (P*rnhub 2019 Year in Review).
- 54% of U.S. teens had seen p*rn by age 13; 15% at 10 or younger (Common Sense Media, 2023, ~1,300 teens).
- Earlier first exposure is linked to more frequent use and higher risk of compulsive use (University of Glasgow systematic review, 2025).
- 10.3% of men and 7.0% of women reported clinically relevant distress from trouble controlling sexual urges/behaviour; 8.6% of adults screened positive (Dickenson et al., JAMA Network Open, 2018, 2,325 U.S. adults).
- 3.2% of 82,243 people across 42 countries were at risk of problematic p*rn use on a conservative measure (up to 16.6% on others); men highest (Bőthe et al., Addiction, 2024, International Sex Survey).
- Only 4–10% of people with problematic p*rn use had ever sought treatment (same study).
- A 2025 study of 2,000+ men linked binge sessions, tab-jumping and tolerance to losing control over p*rn use (Addictive Behaviors, 2025).
- WHO's ICD-11 includes compulsive sexual behaviour disorder (since 2019).
- 56.7% of 1,008 young adults (Rhode Island) had viewed p*rn and 7.9% (~1 in 13) screened positive for p*rn addiction; insomnia was linked to higher odds, mainly in heterosexual men (2024 survey data, published 2025).
- Each extra hour of screen time after going to bed was tied to 59% higher odds of insomnia symptoms (Frontiers in Psychiatry, 2025, ~40,000 Norwegian students). Screens in general, not p*rn specifically — say so.
- Arithmetic is fine: 30 min/day = ~182 hours/year.
- 46% of men aged 18–39 intentionally viewed p*rn in a given week (Journal of Sex Research, nationally representative samples, 2014 data).
- 42% of men aged 18–29 watch p*rn daily or several times a week; another 26% weekly or less (Institute for Family Studies / YouGov, 2026, 2,000 young men — advocacy-linked, say so if asked).
- 21–37% of people with problematic p*rn use wanted treatment but didn't get it, e.g. because of cost (Bőthe et al., Addiction, 2024).
- 26% (about 1 in 4) of men seeking help for new erectile dysfunction at one clinic were 40 or younger (Capogrosso et al., Journal of Sexual Medicine, 2013, 439 patients). One clinic, not population prevalence; doesn't prove p*rn causes ED — always say "see a doctor".
- In 1,755 couples, bigger differences in partners' p*rn use were linked to lower relationship satisfaction and stability, less positive communication and more conflict (Willoughby et al., 2016).
- Secret ("unknown to partner") p*rn use was linked to the user reporting lower relationship satisfaction and intimacy that day (Vaillancourt-Morel et al., 2023, daily-diary study). Short-term effect — say so.
- 36% of daily p*rn users said they feel lonely all or most of the time, vs 20% of those who rarely or never watch (Institute for Family Studies / YouGov, Sept 2024). Correlational — loneliness and p*rn may feed each other.
- 61% of U.S. adults said they view p*rn, up from 55% in 2015; half of users say "no one" knows about their use; 84% say no one helps them avoid it; 39% of Gen Z adults view it daily or weekly (Barna / Pure Desire, "Beyond the P*rn Phenomenon", 2,976 U.S. adults surveyed Oct 2023, published 2024; faith-based publisher — fine to cite, name the source).
- About 21% of 3,419 men aged 18–35 who'd tried sex in the past 4 weeks reported some degree of erectile dysfunction; how often they watched p*rn was NOT linked to ED, but problematic (out-of-control) use was (JMIR Public Health and Surveillance, Belgian survey, 2021/22).
- A 2025 meta-analysis of 21 studies (138,192 adults, North America/Europe/Asia): men who used p*rn reported worse sexual function and lower satisfaction than women who used it. Can't prove cause — say so.

## No repeats (user feedback 17-11-26)
The user noticed repeated posts. Before committing, run `python3 check_repeats.py content/<today>-*.json` — it must
print 0 problems. It flags: topic/hook overlap with any earlier carousel, a stat reused within 7 days, a tip already
used in 2+ carousels, and two carousels on the same day sharing a stat or angle. Never reuse a sample or earlier
carousel. When stats run dry, research and add new verified ones to the stats bank rather than reuse.

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
- 10-11-26 Shalini: early exposure (54% by 13) · "I'm not enough" shame cycle · quitting vs recovering · what to say in the first minute of an urge · p*rn & attention span
- 10-11-26 Tanmay: recovery isn't a leaderboard · p*rn addiction in your 20s · reading about it isn't recovery · p*rn shaping your "type" · 10-item urge emergency list
- 10-11-26 Yash: "I'll quit when life calms down" · in a relationship but still watching · women and p*rn addiction · channeling energy after quitting · morning wake-up p*rn trap
- 11-11-26 Shalini: NNN week-by-week timeline · failed NNN (harsh) · 9 signs you're more addicted than you think · only 4–10% seek help (Bőthe 2024) · week 2 of NNN is the hardest
- 11-11-26 Tanmay: 115M visits a day / 13% of searches (stats) · NNN isn't a joke (harsh) · what daily p*rn does 1 week → 5 years · 8 signs you're escaping your life (harsh) · 11 rules for the rest of NNN
- 11-11-26 Yash: NNN halfway check-in (10 questions) · 1 in 10 men (JAMA 2018) · 7 signs you're ready to quit · nobody is coming to save you (harsh) · first 72 hours after an NNN relapse
- 12-11-26 Shalini: 6 signs NNN is working · can't go 12 days = p*rn is the boss (harsh) · 3.2% is millions (Bőthe 2024) · what you get back 1 day → 1 month · 7 things nobody tells you about quitting
- 12-11-26 Tanmay: not tempted, bored (harsh, NNN) · phone in bed +59% insomnia (Frontiers 2025) · 8 signs p*rn is hurting your relationship · NNN plan Day 12 → 30 · brutal audit of what p*rn cost this year (harsh)
- 12-11-26 Yash: 12 things instead of p*rn tonight (NNN) · 5 signs you're about to relapse (NNN) · 1 in 13 young adults (Rhode Island 2025) · p*rn is not self-care (harsh) · p*rn-free year month 1 → 12
- 13-11-26 Shalini: 13 truths (Friday 13th, NNN) · 7 signs you're doing NNN wrong · ICD-11 + 8.6% (stop calling it a habit) · 20 minutes of an urge, minute by minute · what to say to a friend who relapsed
- 13-11-26 Tanmay: peeking isn't NNN (harsh) · 39B searches (P*rnhub 2019) · 9 signs p*rn hurts work/studies · drinks + Friday night (NNN) · "how long until I'm over it" (harsh)
- 13-11-26 Yash: 2 days from halfway (NNN) · 7 signs it's time to talk to someone · little brother 54% by 13 · "last time" dozens of times (harsh) · NNN weekend plan Fri → Mon
- 14-11-26 Shalini: two weeks without p*rn timeline (NNN) · Saturday is p*rn's favorite day (NNN) · 8 signs your brain is healing · "too busy" (harsh, 182h) · 10.3% + 4–10% silence gap
- 14-11-26 Tanmay: quit today, regret on Nov 30 (NNN) · 6 signs you're one night from relapse (NNN) · running on empty, not weak · 13% of searches / 1 in 8 · first 5 minutes after waking
- 14-11-26 Yash: halfway, update your defenses (NNN) · 7 lies during NNN · 8 signs p*rn kills confidence · 15% at 10 or younger · "I'm a guy, it's natural" (harsh)
- 15-11-26 Shalini: halfway 15 days (NNN, harsh) · 7 signs you'll finish NNN · 3 escalation behaviors (Addictive Behaviors 2025) · Sunday 30-minute reset · p*rn as a reward (harsh)
- 15-11-26 Tanmay: half of you wants p*rn back (NNN) · what a just-once relapse costs (NNN timeline) · 8 signs your use is getting worse · "high sex drive" label (harsh) · 90%+ never get help (Bőthe 2024)
- 15-11-26 Yash: second-half NNN game plan · 9 things you'll stop doing · Day 15 still thinking about p*rn (NNN) · 60+ hours a year on one site (P*rnhub 2019) · your excuses are expired (harsh)
- 16-11-26 Shalini: past halfway, p*rn works harder (NNN) · 6 signs you swapped p*rn for another escape (NNN) · parents: 54% by 13 · Monday reset after a bad weekend · p*rn isn't on your side (harsh)
- 16-11-26 Tanmay: week 3 is boring (NNN) · 7 signs you'll stay free after November (NNN) · "just a phase" for years (harsh) · 1 in 12 adults (JAMA 2018) · 10 small wins in month 1
- 16-11-26 Yash: 14 days left, build one thing (NNN) · 8 signs NNN is changing you · phone = p*rn delivery machine (115M/day) · "just curious" (harsh) · what to tell yourself at 1 AM
- 17-11-26 Shalini: 5 excuses partners hear (myth-buster) · 8 things partners feel · NNN debate: watch but don't finish · 42% of young men almost daily (IFS 2026, NNN) · 15 years in, 5 out: 7 lessons (composite)
- 17-11-26 Tanmay: p*rn made you insecure about your body · "I can stop whenever" Day 17 (harsh) · 24 hours after saying no (NNN) · rejection → p*rn · how often is too often: 5 tests (debate)
- 17-11-26 Yash: friends quit NNN, keep going solo · letter to your Day 1 self (NNN) · your boyfriend has a p*rn problem (partners) · p*rn changes how you see women · is p*rn cheating? (debate)
- 18-11-26 Shalini: wet dream isn't a relapse (NNN myth-buster) · NNN in a relationship: 5 things to tell her (partners) · p*rn gap in couples (Willoughby 2016) · daytime urge at work: 5 tips · stop googling "is p*rn bad" (harsh)
- 18-11-26 Tanmay: 7 things for restless hands (NNN) · No P*rn November instead? (debate) · the conversation p*rn lets you skip · 1 in 4 new ED under 40 (Capogrosso 2013) · your excuse at 14/18/22/26 (harsh timeline)
- 18-11-26 Yash: turning points in recovery stories (NNN, composite) · 30-second NNN check-in text · secret p*rn hits your own intimacy (2023 study) · 6 signs p*rn crept into how you talk about women · deleting the app isn't quitting (harsh)
- 19-11-26 Shalini: 36% of daily users lonely (IFS 2024, NNN) · partners: support without babysitting (NNN) · you want to feel nothing, not p*rn · healing vs self-punishment: 7 tells (NNN) · "waiting for the right moment" to tell her (harsh)
- 19-11-26 Tanmay: 3 AM wake-up urge (NNN) · 46% of men weekly / 3 weeks off (JSR, NNN) · the 3-line urge log · 6 signs your partner already knows · "slip" every weekend = schedule (harsh myth-buster)
- 19-11-26 Yash: holiday trips home / childhood bedroom (NNN) · tell people or keep NNN private? (debate) · 3.2–16.6% screening questions (Bőthe 2024) · the "scan" reflex · too tired to train, not for p*rn (harsh)
- 20-11-26 Shalini: 5 mistakes in the last 10 days (NNN) · 6 reasons secrecy keeps it alive (Barna 2024: half say no one knows, 84%) · 6 things p*rn taught you about sex · 3 reasons you'll go back with 10 days left (NNN, harsh) · 7 habits of people who quit for good
- 20-11-26 Tanmay: 4 reasons December is harder (NNN) · 5 reasons p*rn feels normal to Gen Z (Barna 39%/61%) · 5 reasons willpower alone fails (harsh) · 5 ways to clean your feed · 8 questions for your accountability partner (NNN)
- 20-11-26 Yash: 10 reasons to finish NNN · 6 kinds of free help (Bőthe 21–37%) · 6 signs your reason won't last · 4 mistakes that kill streaks (NNN, harsh) · 5 myths about men who don't watch p*rn (harsh)
- 21-11-26 Shalini: 6 lessons from 3 weeks (NNN) · 4 facts about p*rn and ED (JMIR 3,419 men, ~21%) · 3 types of urges (bored/stressed/autopilot) · 5 rules home alone (NNN, harsh) · 5 signs p*rn affects your mental health
- 21-11-26 Tanmay: 5 reasons you're irritable at 3 weeks (NNN) · 4 reasons you keep searching for something new (39B searches) · 6 ways p*rn steals your weekend (harsh) · 4 kinds of friends who make quitting harder · 8 numbers to track for the last 9 days (NNN)
- 21-11-26 Yash: 5 skills built in 21 days (NNN) · 4 things research says about p*rn and your sex life (meta-analysis 138,192) · 6 phrases when negotiating with p*rn addiction (harsh) · 6 p*rn backdoors to delete before NNN ends (NNN) · 6 ways p*rn kills your ambition (harsh)

## Archive: Reddit inspiration (retired 19-11-26 — did not perform; reference only)
Threads: r/AskMen "What are some signs of an actual p*rn addiction?" (149 comments), r/whatdoIdo "boyfriend has a
p*rn addiction, what do I do?" (557 upvotes, 2K comments), r/selfimprovement "How I made the p*rn addiction go away",
r/PornAddiction confessions ("destroyed my marriage", "led me to something I regret"), r/PornIsMisogyny.
What makes them land — copy the *patterns*, never quote usernames or reproduce posts word for word:
1. **Real-world tests, not theory.** Top AskMen answers were concrete: "choosing p*rn over a willing partner",
   "can't stay aroused with a real person" (top comment), "watching it at work / while driving", "multiple times a
   day", "if it interferes with your life", "a constant fight against your own mind". Make "signs" carousels this
   specific and blunt.
2. **The partner's side is huge.** The girlfriend thread got 2K comments. Partners' questions: Is it my fault? Why
   does he hide accounts? Why does he get defensive? Should I stay? Make carousels *for partners* (Shalini's account
   suits this) and *for men about what partners feel*. Thread insight: "the addiction is one thing — getting
   defensive and dismissive when confronted is another." Don't tell people to leave or stay; give questions/signs.
3. **Excuses called out.** "I watch it for your safety", "it's private, nothing to do with you", "it's just a
   phase", "I can stop whenever" — commenters tore these apart. Turn each into a harsh myth-buster.
4. **First-person recovery voice.** "How I made it go away" style: honest, specific, a turning point ("I realised it
   wasn't p*rn I wanted, it was connection"). Write some carousels as an anonymous composite "what recovered guys
   say" — never present it as one real person's story or invent quotes as real.
5. **Comfort doesn't create change.** "We don't change unless we're uncomfortable"; "rock bottom is usually the
   catalyst"; "replace the habit, one day at a time". Good harsh-but-hopeful lines.
6. **Consequences escalate.** Confessions about broken marriages and regret drew big engagement. Use the *idea*
   (p*rn quietly costs relationships, trust, self-respect) — no graphic or illegal-content details, ever.
7. **Debate hooks drive comments.** "How often is too often?", "Is it cheating if you're in a relationship?",
   "Is it OK if your partner is fine with it?" — ask the question on slide 1, give a clear take, invite replies.

### Round 2 — threads that went big (user says these worked "like crazy"; adapt them, they travel to IG/TikTok)
- **"I overcame 16 years of p*rn addiction, clean for 6 years" (r/PornAddiction, 136↑).** Format = long-haul
  recovery story: started at 14 when the internet got fast → escalated through his 20s → symptoms list (social
  anxiety, performance problems, brain fog, insomnia, numbing with weed, constant lying) → his marriage ended
  *"not because of the p*rn, but because I lied"* → lessons: hiding keeps it alive; transparency is freedom;
  grace and forgiveness free you from shame. Comments asked "what's life like 6 years later?" → answer: real
  relationship, no more performance issues, own business. → Make "X years in, Y years out: what I learned"
  carousels (composite voice) and "what life looks like after quitting" carousels. Hiding/lying > the act itself.
- **"How I made the p*rn addiction go away" (r/selfimprovement, 563↑ — the biggest).** The turning point:
  *"It's ALL THE SAME. It doesn't matter how many videos, how many different people, or how much you pay — it
  never gives you what you actually want."* He'd spent thousands on custom content and realised every "type" he
  chased mirrored a feeling he was avoiding. What he really wanted was connection — someone to say he's good
  enough. Urges faded in ~2 weeks after that realisation. Top comments: "It's a search for connection" (78↑),
  "P*rn isn't really about sex — it numbs underlying pain" (60↑), "P*rn is a coping mechanism, a symptom of
  something else" (30↑). → The single strongest angle: **what you're really looking for isn't p*rn.** Use it
  often, in different words: chasing novelty never lands; your "type" points to the feeling you avoid; paying more
  doesn't fill it.
- **"People with p*rn addiction, this may help u" (r/PornAddiction, 201↑).** Plain numbered tips that anyone can do
  tonight: (1) urge hits → phone down, stare at a wall for 10–20 min and do nothing; (2) **reset your feed** —
  deliberately search wholesome/cute/funny content so the algorithm stops serving suggestive posts; (3) use a
  blocker; (4) have a purpose: *"I love someone and I don't want them to see me as an addict."* A top comment:
  the feed reset is underrated — people quit p*rn but keep every soft trigger in their feed; outside reasons beat
  willpower. → Short, practical, numbered "do this tonight" carousels are highly saveable.
- **r/PornIsMisogyny caption post (326↑).** Angle: p*rn trains contempt and objectification, and partners feel it —
  insecurity, comparing their bodies, feeling targeted. → Carousels on how p*rn changes the way you see women and
  how partners experience it. Keep it about the viewer's habit, never shame performers or women.
- **"My p*rn addiction led me somewhere I never imagined" (r/PornAddiction).** The *lesson only*: escalation can take
  you places you never thought you'd go, and the shame afterwards can feel unbearable. NEVER reference minors,
  illegal content or details. If a carousel touches despair or hopelessness, include: "If you're thinking about
  hurting yourself, contact a crisis line or emergency services now."

