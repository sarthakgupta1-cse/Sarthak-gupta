# YouTube Videos on Porn Addiction & Recovery

A categorised, deduplicated index of **1,016** YouTube videos, playlists and
channels covering pornography addiction: the neuroscience, clinical treatment,
recovery programmes, personal testimony, effects on partners and families,
faith-based approaches, and the scientific debate over whether the diagnosis is
valid at all.

## Contents

| Path | Description |
| --- | --- |
| `data/porn_addiction_youtube_videos.csv` | The index — 1,016 rows, one per video/playlist/channel |
| `data/build_sheet.py` | Original 363-row source table + CSV generator |
| `data/extra_rows.txt` | The 653-row expansion, `@@@`-delimited |
| `data/build_full.py` | Merges both sources, dedupes by video ID, writes the CSV |
| `data/split_parts.py` | Splits the index into category-grouped parts for upload |

Regenerate with:

```sh
python3 data/build_full.py data/porn_addiction_youtube_videos.csv
```

## Columns

| Column | Notes |
| --- | --- |
| `#` | Row number |
| `Title` | Video title as listed on YouTube |
| `Category` | One of 106 topic buckets |
| `Language` | Primary language of the content (31 distinct) |
| `Type` | `Video` (894), `Short` (54), `Playlist` (35) or `Channel` (33) |
| `URL` | Direct link |
| `Video / Playlist ID` | YouTube ID — the deduplication key |
| `Watched?` / `Rating` / `Notes` | Blank, for the reader to fill in |

## Coverage

**Topic:** neuroscience and dopamine · TED/TEDx · clinical treatment, CBT, ACT,
EMDR and IFS · ICD-11 compulsive sexual behaviour disorder · porn-induced ED ·
death grip · NoFap/reboot · No Nut November · 30/90-day challenges · withdrawal
and flatline · relapse prevention · triggers and coping · self-assessment ·
escalation and tolerance · shame and disclosure · intimacy anorexia and
attachment · gooning and brain rot · dopamine detox · AI porn and companion
chatbots · OnlyFans · hentai and VR · ADHD, autism and OCD · personal testimony ·
relationships, spouses and betrayal trauma · teens, students and parents ·
women's experiences · LGBTQ · pastors and church leaders · celebrity interviews ·
12-step groups · blockers and accountability apps · industry and trafficking ·
age-verification policy · and the sceptical case that "porn addiction" is not a
valid diagnosis.

**People and organisations with their own buckets:** Gary Wilson (Your Brain on
Porn) · Dr. K / HealthyGamerGG · Andrew Huberman · Jordan Peterson · Gabor Maté ·
Dr. Trish Leigh · Dr. Doug Weiss · Patrick Carnes / IITAP · Paula Hall · Jay
Stringer · Eddie Capparucci · Gabe Deem / Reboot Nation · Mark Queppet /
Universal Man · Craig Perra / The Mindful Habit · Sathiya Sam · Jeremy Lipkowitz ·
Craig Gross / XXXchurch · Pure Desire / Conquer Series · Fight the New Drug ·
Culture Reframed · Nicole Prause and David Ley (the sceptics).

**Languages (31):** English, Hindi, Urdu, Bengali, Tamil, Telugu, Marathi,
Kannada, Malayalam, Sinhala, Arabic, Persian, Turkish, Russian, Polish, German,
French, Italian, Dutch, Spanish, Portuguese, Chinese, Japanese, Korean,
Vietnamese, Indonesian, Malay, Tagalog, and mixed pairs.

## How the list was built

Titles and URLs were gathered from ~75 web searches scoped to `youtube.com`,
then deduplicated by video ID (zero duplicates survived the merge).

This is a broad sample, not a complete census — YouTube hosts tens of thousands
of videos on this topic and offers no public means of enumerating them all.
YouTube itself is blocked by the build environment's egress policy, so the index
could not be assembled by scraping YouTube search results directly.

Titles and metadata have not been individually verified against each live video,
and view counts, durations and upload dates are not included.

## Note on viewpoints

The list deliberately spans the full range of public discussion, including
positions that contradict each other — the clinical and neuroscience literature,
recovery communities, religious teaching, and researchers who argue that "porn
addiction" is not a valid diagnosis. Inclusion is not endorsement of any
individual video's claims.
