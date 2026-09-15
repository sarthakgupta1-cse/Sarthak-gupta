# YouTube Videos on Porn Addiction & Recovery

A categorised, deduplicated index of YouTube videos, playlists and channels
covering pornography addiction: the neuroscience, clinical treatment, recovery
programmes, personal testimony, effects on partners and families, and
faith-based approaches.

## Contents

| Path | Description |
| --- | --- |
| `data/porn_addiction_youtube_videos.csv` | The index — 363 rows, one per video/playlist/channel |
| `data/build_sheet.py` | Source data + generator that produces the CSV |

## Columns

| Column | Notes |
| --- | --- |
| `#` | Row number |
| `Title` | Video title as listed on YouTube |
| `Category` | One of 39 topic buckets (see below) |
| `Language` | Primary language of the content |
| `Type` | `Video`, `Short`, `Playlist` or `Channel` |
| `URL` | Direct link |
| `Video / Playlist ID` | YouTube ID, for deduplication |
| `Watched?` / `Rating` / `Notes` | Blank, for the reader to fill in |

## Categories

TED / TEDx · General / Overview · NoFap / Reboot · Neuroscience · Your Brain on
Porn (Gary Wilson) · Dr. K / HealthyGamerGG · Porn-Induced ED (PIED) · Clinical /
Therapy · Personal Testimony · Andrew Huberman · Jordan Peterson · Faith
(Christian, Catholic, LDS, Islam, Eastern/Sadhguru) · Gabor Mate / Trauma ·
Women & Porn Addiction · Debate / Is It Real? · Relationships & Marriage ·
Betrayal Trauma / Partners · Teens / Parents · Withdrawal / Flatline · Relapse
Prevention · Signs / Self-Assessment · Escalation / Tolerance · Mental Health
Effects · Fight the New Drug / Documentary · 30/90-Day Challenges · Celebrity
Interviews · Dr. Trish Leigh · Dopamine Detox · 12-Step / Support Groups ·
Blockers / Accountability Tools · Motivation · Podcasts / Long-Form · Hindi ·
Spanish · Portuguese

## How the list was built

Titles and URLs were gathered from web searches scoped to `youtube.com` across
~30 queries spanning the topic areas above, then deduplicated by video ID.

This is a broad sample, not a complete census — YouTube hosts tens of thousands
of videos on this topic and there is no public API for enumerating all of them.
Regenerate or extend the CSV by editing the `ROWS` table in `data/build_sheet.py`
and re-running it.

## Note on viewpoints

The list deliberately spans the full range of public discussion, including
positions that disagree with each other — the clinical and neuroscience
literature, recovery communities, religious teaching, and commentators who argue
that "porn addiction" is not a valid diagnosis. Inclusion is not endorsement of
any individual video's claims.
