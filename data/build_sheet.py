#!/usr/bin/env python3
"""Build a CSV of YouTube videos about porn addiction / recovery.

Every row was gathered from web search results restricted to youtube.com,
then deduplicated by video ID. Columns are designed to be filter-friendly
once the CSV is opened as a Google Sheet.
"""
import csv, re, sys

# (title, category, language, kind, id_or_path)
# kind: video | short | playlist | channel
ROWS = [
# ---------------- TED / TEDx ----------------
("The Great Porn Experiment | Gary Wilson | TEDxGlasgow","TED / TEDx","English","video","wSF82AwSDiU"),
("Pornography Isn't Your Problem | Jason Mahr | TEDxCincinnati","TED / TEDx","English","video","vIgWMzdgweI"),
("Why I stopped watching porn | Ran Gavrieli | TEDxJaffa","TED / TEDx","English","video","gRJ_QfP2mhU"),
("Changing the narrative around the addiction story | Cameron Staley | TEDxIdahoStateUniversity","TED / TEDx","English","video","mNGg5SMcyhI"),
("Escaping Porn Addiction | Eli Nash | TEDxFortWayne","TED / TEDx","English","video","dbYWKVAeu6Y"),
("Let's Talk Porn | Maria Ahlin | TEDxGoteborg","TED / TEDx","English","video","DBTb71UzPmY"),
("Why we need to talk about porn | Jo Robertson | TEDxChristchurch","TED / TEDx","English","video","TCY2dOf2eMs"),
("Healing Addictive Behaviors: My Porn Story | David Norwell | TEDxSurrey","TED / TEDx","English","video","HcbUgEB5A98"),
("How porn is destroying young men | Gary Wilson (Key Points Talk)","TED / TEDx","English","video","3adhnLRoxig"),
("Rethinking Porn: Why Shame, Not Sex, Is the Problem | Paulita Pappel | TEDxMunchen","TED / TEDx","English","video","1mrUIt8CDfI"),
("Porn The New Tobacco | Jack Fischer | TEDxBinghamtonUniversity","TED / TEDx","English","video","M9pPgIraoOM"),

# ---------------- General overview ----------------
("6 Dangerous Stages of Porn Addiction","General / Overview","English","video","w_eG8ulIYug"),
("How to Overcome Porn Addiction","General / Overview","English","video","8Gqb2vhQmxI"),
("Pornography Addiction and Treatment Strategies","General / Overview","English","playlist","PLcB3trehXswg3yz_CGjlkGGDM3FDFb2OZ"),
("Breaking the Cycle of Pornography (Porn) Addiction","General / Overview","English","video","F0w_7_96CJc"),
("Urologist Explains how to break the cycle of porn addiction","General / Overview","English","video","E0AZMtVTIjk"),
("THIS VIDEO WILL END YOUR PORN ADDICTION (Breaking Free From Addiction)","General / Overview","English","video","r6x7BBXyUJc"),
("How to Stop Porn Addiction (Never Relapse Again)","General / Overview","English","video","s4tJmFL20Us"),
("Am I Addicted to Porn? What is Porn Addiction?","General / Overview","English","video","3WOT4NWEFdU"),

# ---------------- NoFap / reboot ----------------
("Quit Porn & Rewire Your Brain In ONLY 16 Weeks | NoFap Reboot","NoFap / Reboot","English","video","KiGRlQocxow"),
("The 2 STEP PROCESS To Quit Porn & Reboot Your Brain | NOFAP SUCCESS","NoFap / Reboot","English","video","16-UQy3K5rE"),
("CHANGE YOUR BELIEFS To Quit Porn & Reboot Your Brain | NOFAP SUCCESS","NoFap / Reboot","English","video","UU5YVFCoyI8"),
("7 Things You Can Do To SPEED UP NoFap Recovery | NoFap Reboot Faster","NoFap / Reboot","English","video","F6XFssY_bvc"),
("How much does a relapse set back your porn reboot?","NoFap / Reboot","English","video","H2f3oaJfkLk"),
("Porn Reboot NoFap Flatline: How to Make NoFap Better with Dr. Trish Leigh","NoFap / Reboot","English","video","w7gyTwfO9QU"),
("How To SPEED UP Your Porn Reboot With ONE DAILY HABIT","NoFap / Reboot","English","video","mv9lDQdI08Q"),
("3 Tips To RECOVER From A PMO RELAPSE | NoFap FAILED Again","NoFap / Reboot","English","video","giasef0M1Bk"),
("How long will it take to reboot my brain from porn?","NoFap / Reboot","English","video","ODx7aYIDIm8"),
("What Can Happen If You DON'T QUIT PORN & REBOOT YOUR BRAIN (NOFAP FAIL)","NoFap / Reboot","English","video","s44HF3dKSx0"),
("NoFap's Alexander Rhodes explains how porn addiction is impacting a generation","NoFap / Reboot","English","video","eot_61u43Gc"),
("Your Brain Rebalanced Radio S02E05: Alex Rhodes (NoFap founder) and Mark Queppet","NoFap / Reboot","English","video","AGHex1jgshs"),
("Alexander Rhodes (playlist)","NoFap / Reboot","English","playlist","PL7aTMa-qEZRLr7HliULP8J_Ek2gM-i_AM"),
("Porn Addiction Coach - Noah Church","NoFap / Reboot","English","video","MmuDe_Og37g"),
("How & Why To Stop Watching Porn with Noah B.E. Church","NoFap / Reboot","English","video","EMmcuHbWFWg"),
("Noah B.E. Church Interview, Author of 'Wack: Addicted to Internet Porn'","NoFap / Reboot","English","video","wcgJeI7BQcg"),
("Noah B.E. Church (channel)","NoFap / Reboot","English","channel","@noahb.e.church"),

# ---------------- Neuroscience ----------------
("How Porn Hooks Your Brain - The Addiction Loop Explained","Neuroscience","English","short","F_tNVNPpPkU"),
("Part 4: Dopamine: The Molecule of Addiction | Your Brain on Porn | Animated Series","Neuroscience","English","video","bdiMFQk_aW8"),
("#033 - Porn Addiction: Dopamine, Disgust, and Erectile Dysfunction (Gary Wilson)","Neuroscience","English","video","EVFrMoN9pik"),
("How Porn Addiction Rewires Your Brain and Destroys Intimacy, Doctor Explains","Neuroscience","English","video","vziyvvWW4eA"),
("Porn Addiction Is Not About Sex - Neuroscience Explained","Neuroscience","English","video","owvcbahb1IE"),
("Why Porn Is Addictive: Dopamine And Brain Chemistry Explained","Neuroscience","English","video","1n7LQt8wTKs"),

# ---------------- Your Brain on Porn (Gary Wilson) ----------------
("Part 1-5: Your Brain on Porn | Animated Series (full)","Your Brain on Porn (Gary Wilson)","English","video","i6gk4lW1hPo"),
("Part 1: Introduction | Your Brain on Porn | Animated Series","Your Brain on Porn (Gary Wilson)","English","video","e2mhQf8RjQs"),
("Part 2: The Coolidge Effect | Your Brain on Porn | Animated Series","Your Brain on Porn (Gary Wilson)","English","video","EQuppzt1yEc"),
("Part 3: The Reward Circuit | Your Brain on Porn | Animated Series","Your Brain on Porn (Gary Wilson)","English","video","uSEo2miwnZQ"),
("Part 5: Pornography Addiction Test | Your Brain on Porn | Animated Series","Your Brain on Porn (Gary Wilson)","English","video","26_BGVm2M0k"),
("Your Brain On Porn (Animated Summary) | Gary Wilson","Your Brain on Porn (Gary Wilson)","English","video","mDwE8jYnw2M"),
("Your Brain on Porn by Gary Wilson - Book Summary","Your Brain on Porn (Gary Wilson)","English","video","yZK6eZCYH1Y"),
("Remembering Gary Wilson of Your Brain On Porn: My Friend & Hero","Your Brain on Porn (Gary Wilson)","English","video","kXaqKRbKfog"),
("Part 3: The Reward Circuit | Your Brain on Porn in Urdu | Animated Series","Your Brain on Porn (Gary Wilson)","Urdu","video","AHEhXjEvU3A"),
("Gary Wilson | Your Brain On Porn (Episode 158)","Your Brain on Porn (Gary Wilson)","English","video","xL2gHbpPMtg"),

# ---------------- Dr. K / HealthyGamerGG ----------------
("Porn Addiction Is Misunderstood: How To Actually Stop - Dr. K Healthy Gamer","Dr. K / HealthyGamerGG","English","video","y1CkUhfHSxQ"),
("Helping Viewers with Porn Addiction","Dr. K / HealthyGamerGG","English","video","e1ndqAkiQZo"),
("Why Pornography Addiction is MISUNDERSTOOD (It's NOT What You Think) With Dr K","Dr. K / HealthyGamerGG","English","video","jWIWFB3Ber8"),
("The Neuroscience Of Porn Addiction: How To Actually Stop - Dr. K Healthy Gamer","Dr. K / HealthyGamerGG","English","video","jR1IDcdC2DM"),
("Dr. K Healthy Gamer Talks About Porn Addiction","Dr. K / HealthyGamerGG","English","video","qlQx-Dk7Q3E"),
("Sexuality and Porn | Healthy Gamer (playlist)","Dr. K / HealthyGamerGG","English","playlist","PLYxtGyYUCbEEcbuWAXjOsqp8iB0Lf3K8_"),
("How your diet combats p**n addiction","Dr. K / HealthyGamerGG","English","video","Jq74p0Z2o5A"),
("Biggest Predictor Of P*rn Addiction | Dr K Healthy Gamer","Dr. K / HealthyGamerGG","English","video","pjbDuKwj1wA"),
("The Science Of Screen Addiction & How To Stop - Dr K Healthy Gamer","Dr. K / HealthyGamerGG","English","video","HYiG2m8fSiE"),
("The Porn Addiction Crisis No One Wants to Talk About - Dr. K","Dr. K / HealthyGamerGG","English","video","dm2qDrb3UVo"),

# ---------------- Porn-induced ED ----------------
("Can Pornography Cause Erectile Dysfunction? | Top Tips to Naturally Reverse ED","Porn-Induced ED (PIED)","English","video","QKMbNHddceA"),
("Porn-Induced Erectile Dysfunction Is Real - Joe Rogan Was Right About NoFap","Porn-Induced ED (PIED)","English","video","jBy7JzIf4TY"),
("Day 13: Porn-Induced Erectile Dysfunction: How to Heal It w/ Dr. Trish Leigh","Porn-Induced ED (PIED)","English","video","IbqL6BzZ4rg"),
("The Truth Of Porn Induced ED (PIED) - Dr. Trish Leigh","Porn-Induced ED (PIED)","English","video","YDM9I5yn4ZE"),
("Can Watching Porn Cause Erectile Dysfunction? - Doctor Explains","Porn-Induced ED (PIED)","English","video","aqbauFKg-SI"),
("Porn Induced Erectile Dysfunction - Dr. Kelkar (MD) Psychiatrist","Porn-Induced ED (PIED)","English","video","kbdy7RKZBSo"),
("The Truth About Porn-Induced Erectile Dysfunction (From a Sex Therapist)","Porn-Induced ED (PIED)","English","video","eUFfugscMOU"),
("How To Overcome Porn Induced Erectile Dysfunction","Porn-Induced ED (PIED)","English","video","qaB9k7-0NgQ"),
("Is Porn The Reason For Your Erectile Dysfunction? The Science Explained","Porn-Induced ED (PIED)","English","video","QV8e43LV7fc"),
("Porn Induced Erectile Dysfunction - New Age of Tech","Porn-Induced ED (PIED)","English","video","UbzoFAiyWNs"),
("Coach Noah Church on How to Recover from Porn-Induced ED","Porn-Induced ED (PIED)","English","video","HlpYNYRBLw4"),

# ---------------- Clinical / therapy ----------------
("How to CURE a porn addiction? - Doctor Explains","Clinical / Therapy","English","video","RgKhA2qDdBg"),
("Porn Addiction Therapy Treatment And Recovery","Clinical / Therapy","English","video","nkRNxS0dr9g"),
("Pornography Addiction Recovery: The Basics","Clinical / Therapy","English","video","TR6b8t5veo4"),
("TREATING PORNOGRAPHY ADDICTION","Clinical / Therapy","English","video","avrC8mifXug"),
("Pornography Addiction EXPERT Shares Top Relapse Prevention Strategies","Clinical / Therapy","English","video","HZOcI8zxVKs"),
("Break the Cycle of Pornography Addiction | Ryan Soave & Dr. Andrew Huberman","Clinical / Therapy","English","video","wvCTiY4clyM"),
("What Porn Addiction Recovery Actually Looks Like","Clinical / Therapy","English","video","Uv_0ntbirEw"),
("Therapist Reveals the Relationship Between Adult Entertainment and Addiction","Clinical / Therapy","English","short","IAJa22JFeWM"),
("Porn Addiction: Treatment Without Shame (Clip)","Clinical / Therapy","English","video","RKNXejsZmtM"),
("Compulsive Sexual Behavior Disorder ICD-11","Clinical / Therapy","English","video","4mvK8dXpW24"),
("Dr. Stephanie Carnes discusses Compulsive Sexual Behavior Disorder","Clinical / Therapy","English","video","UvdUaIC8NH0"),

# ---------------- Personal testimony ----------------
("Celebrate Recovery Testimony: Blair Shares Her Story of Overcoming Pornography Addiction","Personal Testimony","English","video","6_3-jqkZkkw"),
("Scott's Story: Overcoming a 25-year Porn Addiction (Part 1)","Personal Testimony","English","video","BuGTlykrzu4"),
("Celebrate Recovery Testimony: Mason shares his victory over alcohol, drugs, and porn","Personal Testimony","English","video","Wle79tOhX0E"),
("Sex Addiction Recovery Success Story (Counseling Intensive Testimony)","Personal Testimony","English","video","k1DbmZsSo0U"),
("I Couldn't Break My Porn Addiction, UNTIL I Did This...","Personal Testimony","English","video","YKwqtnAb_F4"),
("Overcoming Pornography Addiction | Carter's Story","Personal Testimony","English","video","0Tm4gjLBxAc"),
("Delivered From 40 Years of Pornography Addiction | Testimony","Personal Testimony","English","video","lxBvRpou6Vo"),
("I WAS ADDICTED TO P0RN FOR 10 YEARS | MY STORY OF HOW I OVERCAME ADDICTION","Personal Testimony","English","video","OGLzufmqXEc"),
("7 Years Trapped in Porn Addiction & Shame - My Testimony","Personal Testimony","English","video","ty-VKqvM_1A"),
("How God SAVED Me From My P*rn Addiction (MY TESTIMONY)","Personal Testimony","English","video","dwFpVHZWxDg"),
("My Personal Journey Escaping Porn Addiction: Eli Nash | THAT'S AN ISSUE podcast Ep 11","Personal Testimony","English","video","-mBN18201h4"),

# ---------------- Huberman ----------------
("The Truth About Pornography | Dr. Jordan Peterson & Dr. Andrew Huberman","Andrew Huberman","English","video","lJlX37bnPnE"),
("If You Take A Break From Watching Porn, This Happens - Andrew Huberman","Andrew Huberman","English","video","9qJHRvHU8IM"),
("'Pornography is a Great Way to NOT Seek Women Out for Sex' REACTION","Andrew Huberman","English","video","BEVG_0GHhFQ"),
("The Truth About Pornography | Dr. Jordan Peterson + Dr. Andrew Huberman (alt cut)","Andrew Huberman","English","video","SVaUzx1wOh8"),
("Andrew Huberman: Explains What 30 Days Without Porn Does","Andrew Huberman","English","video","u6TVPwxHSIk"),
("The Science Behind P*rn Addiction is Scary","Andrew Huberman","English","video","H4gUzdhnFv8"),
("The Dangers of Porn Addiction ft. Andrew Huberman","Andrew Huberman","English","video","X7RMGUl_zSc"),
("PORN: The Digital Cocaine (w/ Jordan Peterson & Andrew Huberman)","Andrew Huberman","English","video","4z_P5wR1JuM"),
("How to Quit Video Game, Pornography & Social Media Addiction | Dr. Andrew Huberman","Andrew Huberman","English","video","XXYNvwrVKdE"),
("Why 90 Days of Being Porn Free? | NEUROSCIENTIST Andrew Huberman","Andrew Huberman","English","video","c7VCzQ9gt4o"),

# ---------------- Jordan Peterson ----------------
("How You Got Addicted to P*rn","Jordan Peterson","English","video","H-ep8lFdZbA"),
("99% Effective way to Stop Watching Porn | Jordan Peterson","Jordan Peterson","English","video","lPMtDDFWZsE"),
("Jordan Peterson Explains What To Do With Your Porn Addiction","Jordan Peterson","English","video","6vOECW-k_4A"),
("Jordan Peterson On Porn Addiction","Jordan Peterson","English","video","9hLnhfLqj-k"),
("Masturbation to Porn Is An Addiction | Jordan Peterson","Jordan Peterson","English","short","Q6PvfMqA50I"),
("Inside the mind of a P*rn addict | Jordan Peterson","Jordan Peterson","English","video","ZsuChK6824Y"),
("Jordan Peterson Discussing Porn Addiction","Jordan Peterson","English","video","IS4cq8ABG6Q"),
("Dr. Peterson on How Porn Is Destroying Young Men","Jordan Peterson","English","video","8UYH4We6_Rw"),
("Dr. Jordan Peterson Explains The Dangerous Effects of Porn","Jordan Peterson","English","video","FbBAHE76YaQ"),
("OVERCOME PORN ADDICTION | Jordan B Peterson Motivational Speech","Jordan Peterson","English","video","Ijy4YntYcD4"),
("How To Stop Watching Porn The Simple Way - Jordan Peterson Motivation","Jordan Peterson","English","video","REjKAmFg8MU"),

# ---------------- Christian ----------------
("Overcoming Pornography Addiction: The Healing Power of Jesus Christ","Faith - Christian","English","video","iXXQpTgSSD8"),
("How To Stop Pornography, Sexual Sin & Masturbation | Apostle Joshua Selman","Faith - Christian","English","video","m6WuLKsaBa8"),
("How I Quit My Porn Addiction For Good - A Christian Perspective","Faith - Christian","English","video","eMA0rX_5sOg"),
("How to Overcome Your Addictions | Tony Evans Sermon","Faith - Christian","English","video","x7wB9Azs-hk"),
("A PRAYER TO OVERCOME PORNOGRAPHY ADDICTION","Faith - Christian","English","video","AAz7NLHfrfQ"),
("HOW JESUS BROKE MY PORNOGRAPHY ADDICTION","Faith - Christian","English","video","WuD1F2iKNa0"),
("How to Stop Watching Porn in 2025 (3 Biblical Steps)","Faith - Christian","English","video","vupXkFoSowM"),
("Quit Porn Addiction By Thinking Differently - A Christian Perspective","Faith - Christian","English","video","-Nd9ZblP2j4"),
("The Biblical Way to Rewire Your Brain Away From Porn","Faith - Christian","English","video","xobB9gLNsik"),
("You've Painfully Tried To Stop Masturbation & Pornography, Do This Now! | Apostle Joshua Selman","Faith - Christian","English","video","kFK7uMPhz9M"),

# ---------------- Catholic / Matt Fradd ----------------
("Matt Fradd interview on combatting addiction","Faith - Catholic","English","video","hqAYSMBByjg"),
("Overcoming Pornography Addiction (Matt Fradd)","Faith - Catholic","English","video","E9RzJGuUdOE"),
("Matt Fradd - Battle Plan for Ministering to a Porn-Addicted Culture","Faith - Catholic","English","video","jE2clKsQtrM"),
("What to do when a spouse is addicted to pornography","Faith - Catholic","English","video","AeMjPgyFPSw"),
("Here's the REAL Problem with Pornography (w/ Matt Fradd)","Faith - Catholic","English","video","ucQ80i76GHI"),
("Catholic Answers Presents 'Taking Down Goliath'","Faith - Catholic","English","video","aCw4qQsewUU"),
("Busting Porn Myths & How to Break a Pornography Addiction - Matt Fradd | American Thought Leaders","Faith - Catholic","English","video","3uhdFdcXHXg"),
("Supporting a Recovering Porn User","Faith - Catholic","English","video","gmPjT2CYAj4"),
("Is porn addiction a myth? (with Matt Fradd)","Faith - Catholic","English","video","2I7GP7SKdz4"),
("Helping Women Heal From Porn Addiction | EWTN News In Depth","Faith - Catholic","English","video","4SEKRPE15bY"),

# ---------------- LDS ----------------
("LDS Addiction Recovery For Porn Addiction","Faith - LDS","English","video","Ha-jCnmV1uw"),
("Surviving LDS Church 12-Step Pornography 'Addiction' Program","Faith - LDS","English","video","JAo_S7k0lKk"),
("#1348: Surviving the LDS Church's 12-Step Pornography 'Addiction' Program with MasterPeace","Faith - LDS","English","video","FTvQvBtZtDw"),
("Healing From Pornography Addiction | 3 Mormons","Faith - LDS","English","video","p8mwP0d4jBc"),
("Mormon 12-Step Addiction Recovery Program (playlist)","Faith - LDS","English","playlist","PLv5QBdw3FlhQW-r_zpRWMQK6wYg34r-oc"),
("Help Overcoming Pornography (playlist)","Faith - LDS","English","playlist","PLAYgY8SPtEWHfaVvDlZvMEvSO2OnfzXXb"),
("Twelve Steps to Recovery","Faith - LDS","English","video","w8y2RyQz44M"),
("Step 1: Honesty - David's Story about Sex Addiction Recovery","Faith - LDS","English","video","W_DtmXXpw6Q"),
("Forgiveness in Overcoming Pornography","Faith - LDS","English","video","1FiyyhDUeBE"),

# ---------------- Islam ----------------
("How to stop watching porn | Mufti Menk","Faith - Islam","English","video","g8M-a2HHp6M"),
("Solution to Stop Watching Pornography In Islam - Animated","Faith - Islam","English","video","MfutmhTe-v4"),
("How I Quit Porn & Masturbation as a Muslim (My 6-Year Battle)","Faith - Islam","English","video","sB7tL9uBHXM"),
("Prayer to overcome porn addiction - Mufti Menk","Faith - Islam","English","video","dWF5hLW2t-c"),
("5 WAYS TO STOP WATCHING PORN IN ISLAM | Nouman Ali Khan","Faith - Islam","English","video","xUsasjxb9q0"),
("How To Quit Porn Addiction In Islam: A Guide for Muslim Youth | Mufti Menk","Faith - Islam","English","video","Bb7Fnce37e4"),
("How To Stop Masturbating In Islam","Faith - Islam","English","video","c92pDmWx558"),
("HOW TO QUIT PORN ADDICTION (Tips & Tricks) - Animated","Faith - Islam","English","video","46TbX6m-foI"),
("I made an oath to stop watching pornography but I keep doing it #hudatv","Faith - Islam","English","video","E_PuNmE36P4"),
("Ultimate Islamic Guide To Masturbation Addiction","Faith - Islam","English","video","7BmTOLRllKI"),

# ---------------- Sadhguru / Eastern ----------------
("Porn Addiction Can Ruin Your Life - Sadhguru","Faith - Eastern / Sadhguru","English","video","tYIkfkGJxTE"),
("Porn Addiction Is Ruining Your Brain | Sadhguru","Faith - Eastern / Sadhguru","English","video","D4FjROvGL6g"),
("Break Free from Porn Addiction! Sadhguru Explains How to Stop Objectification of Women","Faith - Eastern / Sadhguru","English","video","uQhkX3FehUo"),
("Watch this before you watch the Pornography | Sadhguru on how to stop this addiction","Faith - Eastern / Sadhguru","English","video","afojRbb7ad4"),
("Why is Pornography the Biggest Thing on the Internet? - Sadhguru","Faith - Eastern / Sadhguru","English","video","yw8bpB5L8xo"),
("Get best solution of PORN addiction from Sadhguru #UnplugWithSadhguru","Faith - Eastern / Sadhguru","English","video","CrQzmGksWAE"),
("100% DANGEROUS | SAVE YOURSELF FROM THIS ONLINE SICKNESS | SADHGURU","Faith - Eastern / Sadhguru","English","video","B_FqpJXptHk"),
("Porn Addiction | I Can Help: Brahmacharya Samadhi | Podcast Against Lust Industry","Faith - Eastern / Sadhguru","English","video","7NUnL0LVGMU"),
("Sadhguru | WHY You Should STOP Watching This | PORNOGRAPHY | Negative Impact","Faith - Eastern / Sadhguru","English","video","WvWThaDxRQY"),
("Porn Addiction Can Ruin Your Life - Sadhguru | Shemaroo Spiritual Life","Faith - Eastern / Sadhguru","English","video","McX21kgLP94"),
("Porn ki lat aapka jeevan barbaad kar degi | Porn Addiction | Sadhguru Hindi","Faith - Eastern / Sadhguru","Hindi","video","SPTHHcQ0dzE"),

# ---------------- Gabor Mate ----------------
("Pornography addiction treated by boxing | Dr Gabor Mate","Gabor Mate / Trauma","English","short","FPlbK0A4y5U"),
("Gabor Mate On Sexual Abuse","Gabor Mate / Trauma","English","video","OHU_lMSjBFg"),
("Is Porn about S*x? Dr. Gabor Mate","Gabor Mate / Trauma","English","video","LprjJ0JI36E"),
("Hooked: Dr Gabor Mate on Trauma & Addiction | Full Interview","Gabor Mate / Trauma","English","video","oY928d4uzew"),
("Dr. Gabor Mate - Healing Trauma & Addiction","Gabor Mate / Trauma","English","video","JIMlxVBPsy8"),
("Dr Gabor Mate on Addiction, Trauma & Why You Were Never Broken","Gabor Mate / Trauma","English","video","QZHap9gp-_A"),
("Gabor Mate Reveals What Sex Addiction Is Really About","Gabor Mate / Trauma","English","short","SgSC_Ad9vXw"),
("La PSICOLOGIA de un ADICTO a la PORNOGRAFIA | GABOR MATE","Gabor Mate / Trauma","Spanish","video","MoKJw3PF-wA"),

# ---------------- Women ----------------
("Porn Addiction in Women: Breaking the Silence on the Invisible Struggle","Women & Porn Addiction","English","video","jOWTi9qscTo"),
("Porn Addiction Isn't Just a Male Problem | Women Struggle as Well","Women & Porn Addiction","English","video","suzU16nTFO0"),
("Porn Addiction In Women","Women & Porn Addiction","English","short","VYFOgE6U4dk"),
("Pornography - a Women's Problem Too: Practical tips to overcome porn addiction (S03 EP07)","Women & Porn Addiction","English","video","tt4pTEmHcAM"),
("She had a Porn Addiction - She Now Lives in Freedom","Women & Porn Addiction","English","video","SPuLfRsCmxo"),
("Being a girl who struggles with a porn addiction","Women & Porn Addiction","English","video","vO1Skcou5ik"),
("I was a Porn ADDICT | Jessica Harris","Women & Porn Addiction","English","video","tCrKrIEhVmM"),
("I'm A Woman With A Porn Addiction","Women & Porn Addiction","English","video","7OkMTmGdWxY"),
("Porn Addiction | A Woman's Experience","Women & Porn Addiction","English","video","aYLtu3fkW0Y"),

# ---------------- Debate ----------------
("Lamar Odom and Vlad Debate If Porn Addiction is Real (Part 27)","Debate / Is It Real?","English","video","osywiiaFi8Y"),
("Is Porn Addiction Real? | Truth Behind Porn Addiction Explained","Debate / Is It Real?","English","video","6JK6UAPwpQE"),
("Is Porn Addiction Real? What Experts and Former Consumers Want You to Know","Debate / Is It Real?","English","video","sZM3BKXGhG0"),
("EXPOSED: the truth about porn addiction and its links to breaking the law, anxiety and depression","Debate / Is It Real?","English","video","eMLgy5ih7C8"),

# ---------------- Relationships ----------------
("Surprising Pornography Side Effects on Relationships (Porn Addiction)","Relationships & Marriage","English","video","5SbB5Z7L9QE"),
("How Porn Addiction Affects Relationships and What to Do About It","Relationships & Marriage","English","video","NnkdsF0ZUso"),
("How Porn Destroys Relationships (The Brain Science)","Relationships & Marriage","English","video","9UTQebgf6yc"),
("How Porn Addiction Can End Your Marriage","Relationships & Marriage","English","video","TS7Bl0kjpes"),
("How Porn Addiction Ruins Relationships (and How to Heal)","Relationships & Marriage","English","short","1MF5jYEkA-A"),
("Why is Porn So Destructive in Marriage?","Relationships & Marriage","English","video","fH81yvNQrDg"),
("Why Porn Secretly Hurts Your Wife and Family More Than You Realize","Relationships & Marriage","English","video","-jX3MmFk9ME"),

# ---------------- Betrayal trauma ----------------
("Porn Addiction & Betrayal Trauma: A Therapist Explains the Couple's Side","Betrayal Trauma / Partners","English","video","dauKIsC2WT4"),
("How To Help My Wife Heal From Betrayal Trauma","Betrayal Trauma / Partners","English","video","28Dk3bnHMe0"),
("He's a Good Man, But a Porn Addict: How to Recover When You Choose to Stay","Betrayal Trauma / Partners","English","video","QzKfkXREilI"),
("Healing for a Betrayed Partner/Spouse in Therapy; Betrayal Trauma","Betrayal Trauma / Partners","English","video","9rtYFnaXi14"),
("How to help my wife deal with betrayal trauma triggers","Betrayal Trauma / Partners","English","video","0Ok47lMZkfA"),
("Betrayal Trauma Recovery (channel)","Betrayal Trauma / Partners","English","channel","@BtrOrg"),
("Hope & Healing from Betrayal Trauma, Pornography and Sexual Addiction","Betrayal Trauma / Partners","English","video","08MbhofthIM"),
("Why Do I Feel Traumatized by My Husband's Porn Use? | The Neuroscience of Betrayal Trauma","Betrayal Trauma / Partners","English","video","APCIkEPIeYQ"),
("How To Recover From Your Husband's Pornography Addiction?","Betrayal Trauma / Partners","English","video","PLorF9JYZLc"),
("Betrayal Trauma - the Impact of Sex & Porn Addiction on The Wife/Spouse/Partner","Betrayal Trauma / Partners","English","video","78oEcI4aSoQ"),

# ---------------- Teens / parents ----------------
("Yes, Teens have porn ADDICTION symptoms - Here's what parents should do","Teens / Parents","English","video","awiNXDn9Pn0"),
("Breaking Your Teen's Porn Addiction: A Parent's Guide","Teens / Parents","English","video","h-9B8hvwGRU"),
("Teen Who Was Addicted to Pornography Has A Warning for All Parents","Teens / Parents","English","video","8zn-g-14iik"),
("Episode 23: Help Your Teen Beat Porn Addiction: Visualize Their Dream Family Future!","Teens / Parents","English","video","1KAm_Mxj6No"),
("Episode 22: The Hidden Lies Your Teen Believes: How Self-Deception Fuels Porn Addiction","Teens / Parents","English","video","36wP4NS5BBM"),
("How can I help my teen struggling with a pornography addiction? (Full Video) - CCEF","Teens / Parents","English","video","ZzMLt-2AunQ"),
("Teens addicted to porn: What can parents say?","Teens / Parents","English","video","7snp5-AvGQs"),
("Episode 5: Unlocking Recovery: Open Communication to Help Your Teen Overcome Pornography Addiction","Teens / Parents","English","video","scXddKxR4kQ"),
("How To Talk To Your Child About Porn","Teens / Parents","English","video","wnfUlQFIYSQ"),
("How to Talk to Teenagers About Porn | Child Mind Institute","Teens / Parents","English","video","82Tal13t2PA"),
("Pornography Harms","Teens / Parents","English","video","v3AaugTLoZA"),
("Porn: The Conversation That Protects Your Kids | Chris McKenna","Teens / Parents","English","video","WzEwHBQ5lNQ"),
("How to talk to your kids about porn","Teens / Parents","English","video","a7ma-mRCvIw"),
("Porn Exposure Is Harming Kids. What Can Parents Do About It?","Teens / Parents","English","video","cz70-aFYG0s"),
("By age 11, most kids today have already been exposed to pornography","Teens / Parents","English","video","V5dF6LHCK68"),
("6 Things to Do If Your Kid Sees Pornography","Teens / Parents","English","video","llvY9VqJO3M"),
("Protecting Kids from Inappropriate Online Content","Teens / Parents","English","video","sQNFIBH-rjg"),
("Parenting: Talking to Kids About Porn","Teens / Parents","English","video","olg0OWhi3Q4"),

# ---------------- Withdrawal / flatline ----------------
("Porn Addiction Withdrawal Symptoms","Withdrawal / Flatline","English","short","GOxNyo5eqgs"),
("PORN Withdrawal TIMELINE (what to expect)","Withdrawal / Flatline","English","video","H1IlMIgYauw"),
("Porn Addiction Withdrawal Symptoms (w/ Dr. Trish Leigh)","Withdrawal / Flatline","English","video","u5Pj0qly7rE"),
("Dealing With FLATLINE Symptoms While QUITTING PORN","Withdrawal / Flatline","English","video","3dWUz4WpEYc"),
("Reboot Challenges - Withdrawal Symptoms From Porn","Withdrawal / Flatline","English","video","dxtQq0jBncc"),
("How To Stop Porn Withdrawal Symptoms And Avoid Relapse","Withdrawal / Flatline","English","video","taKSpvQuw64"),

# ---------------- Relapse prevention ----------------
("Four Powerful Relapse Prevention Tips | How To Stop Porn Addiction","Relapse Prevention","English","video","Jw-E8G26kyQ"),
("Porn Addiction Aesey Khatam Karein! | How to Stop Porn Addiction - Dr. Zee","Relapse Prevention","Urdu / Hindi","video","-pVgJoChaEA"),
("How To Stop Relapsing To Porn (Scientifically Proven Techniques)","Relapse Prevention","English","short","i2JCSi7EacM"),
("How To Overcome Porn Addiction: Stages, Relapse Prevention & Recovery Tips","Relapse Prevention","English","video","PPWp_X9YccA"),
("How to Quit Porn - 12 Science-Based Strategies for Porn Addiction","Relapse Prevention","English","video","Gul2SRqChpo"),
("Quit Porn - How to Stop Relapsing","Relapse Prevention","English","video","2wx3HXdYwcA"),
("How Can I Avoid Relapses with Pornography Use?","Relapse Prevention","English","video","gOedZQM2UjY"),

# ---------------- Signs / symptoms ----------------
("8 Signs of a Porn Addiction","Signs / Self-Assessment","English","short","5JmteZIWBy4"),
("Porn Brain Quiz: Are You An Actual Addict?","Signs / Self-Assessment","English","video","JL8mcqd93YQ"),
("Porn Addiction Symptoms | You Don't Notice Until It's Too Late","Signs / Self-Assessment","English","video","t7PYltOYgic"),
("7 Signs of Porn Addiction","Signs / Self-Assessment","English","short","j6tCqFhmgpo"),
("7 Porn Addiction Symptoms WATCH OUT FOR","Signs / Self-Assessment","English","video","PTAk3EkJtqQ"),
("Are You Addicted to Porn? Here are the Warning Signs","Signs / Self-Assessment","English","video","ziOT3reMQfY"),
("Porn Addiction Symptoms | Brain Science, Recovery, and Mental Health Insights","Signs / Self-Assessment","English","video","KvXqOthNZo8"),
("Porn Addiction Case Study: Signs and Symptoms","Signs / Self-Assessment","English","video","8vgEITJe8dM"),
("Porn Addiction Symptoms You Shouldn't Ignore | Mental Health Awareness","Signs / Self-Assessment","English","video","RP3KkY2tt2U"),
("Are You Addicted To Porn? | Addiction Test!","Signs / Self-Assessment","English","video","vE8-GcGVhM0"),

# ---------------- Escalation ----------------
("Porn: An Escalating Addiction","Escalation / Tolerance","English","video","CiQ_DNge6zw"),
("Masturbation Escalation | Why Your Brain Always Demands More Extreme Content","Escalation / Tolerance","English","video","ALBLFUD1NNw"),
("Unveiling the Dark Truth: The Escalation of Porn Addiction","Escalation / Tolerance","English","video","ONqwVDvGLTc"),
("Porn escalation is usually unavoidable","Escalation / Tolerance","English","video","7inFElb1GzE"),
("ZERO Tolerance Porn Addiction","Escalation / Tolerance","English","short","MGvzNi1rS8Y"),

# ---------------- Mental health ----------------
("Porn Increases Social Anxiety | How to Improve It w/ Dr. Trish Leigh","Mental Health Effects","English","video","1Z9nok8outw"),
("Why Your Porn Addiction Causes Anxiety & Depression","Mental Health Effects","English","video","XvwH_AG110s"),

# ---------------- Fight the New Drug ----------------
("Fight the New Drug (channel)","Fight the New Drug / Documentary","English","channel","fightthenewdrug"),
("Addiction to porn: It's not about religion - #FightTheNewDrug","Fight the New Drug / Documentary","English","video","InVExUIbPBQ"),
("A Drug Called Pornography - Documentary on Porn (playlist)","Fight the New Drug / Documentary","English","playlist","PLF840BE4348867B2E"),
("Fighting Against Pornography with Clay from Fight the New Drug","Fight the New Drug / Documentary","English","video","4OHaqaLOAf4"),
("Explore Fight the New Drug's collection of resources","Fight the New Drug / Documentary","English","video","LU1etxvlTrY"),
("Fight The New Drug With Clay Olsen","Fight the New Drug / Documentary","English","video","DNRF2_nbjUk"),
("'Brain, Heart, World' | Documentary Series Trailer","Fight the New Drug / Documentary","English","video","_aIXdMzHAcs"),
("Learn More About Fight The New Drug's Presentations","Fight the New Drug / Documentary","English","video","2tH1eWM_-wg"),
("Brain. Heart. World - Episode Two (Heart) Trailer","Fight the New Drug / Documentary","English","video","7wXEH-LPZEE"),
("'Brain, Heart, World' Documentary Series (playlist)","Fight the New Drug / Documentary","English","playlist","PLvFhr3e6CcV3eL-dA-vVkOIHi0w1Y3Itx"),
("'The Brain' Trailer II | 'Brain, Heart, World' Documentary Series","Fight the New Drug / Documentary","English","video","y1GLihr8qR0"),
("Brain.Heart.World - Documentary (Pt.3 'World')","Fight the New Drug / Documentary","English","video","DnMFuVK5SXg"),
("Episode Trailer: 'The Brain' | Brain, Heart, World Documentary Series","Fight the New Drug / Documentary","English","video","tpZrFMUzya0"),
("Episode Trailer: 'The World' | Brain, Heart, World Documentary Series","Fight the New Drug / Documentary","English","video","D0gTu2ZKLpc"),
("'The Heart' Trailer II | 'Brain, Heart, World' Documentary Series","Fight the New Drug / Documentary","English","video","Io8rtXwKLYI"),

# ---------------- 30/90 day challenges ----------------
("All benefits for 90 days NoFap (complete guide)","30/90-Day Challenges","English","video","89qKCPfQDwE"),
("90 days without masturbation and pornography | NoFap challenge can change your life","30/90-Day Challenges","English","video","-ddd23bv8fs"),
("90 Days of NoFap | Quitting Internet Pornography","30/90-Day Challenges","English","video","6xPEShgWgjE"),
("All benefits for 30 days NoFap (complete guide)","30/90-Day Challenges","English","video","48srZi3Fk1M"),
("90 Days of NoFap (4 Life-Changing Benefits)","30/90-Day Challenges","English","video","15hwmRndjL4"),
("What Quitting Porn For 90 Days Does To Your Brain","30/90-Day Challenges","English","video","pOK2CuLTw2Y"),
("3 Scientific Benefits of NoFap (Truth After 90 Days)","30/90-Day Challenges","English","video","nIpaxRXA9Jo"),
("Benefits of NoFap 90 Days Challenge","30/90-Day Challenges","English","video","pPyaHMXkTXk"),
("What Happens When You Quit Porn for 30 Days","30/90-Day Challenges","English","video","baMKuz9ecvU"),

# ---------------- Celebrities ----------------
("Celebrities Getting Real About Porn Addiction: Terry Crews, Mike Tyson, Joe Rogan, Russell Brand","Celebrity Interviews","English","video","RNnzUpGk7Ng"),
("Terry Crews Opens up about Porn Addiction","Celebrity Interviews","English","video","ULSk_6KceEI"),
("Terry Crews on Thirty Year Marriage, Porn Addiction & Cancel Culture","Celebrity Interviews","English","video","HN3k35GYtg4"),
("NoFap: 9 Ways Porn Will Ruin You (Jordan Peterson, Joe Rogan and Terry Crews)","Celebrity Interviews","English","video","j3cfKOkQD9M"),
("How Terry Crews Overcame Porn Addiction | WWHL","Celebrity Interviews","English","video","RYRdFljRgdY"),
("'I Was Addicted to P*rnography' | #ABtalks with Terry Crews | Chapter 249","Celebrity Interviews","English","video","mU9oJkDdAZU"),
("Terry Crews on Porn Addiction | Howie Mandel Does Stuff","Celebrity Interviews","English","video","6sU4jeY3S5I"),
("Terry Crews e Mike Tyson | Joe Rogan Experience Legendado","Celebrity Interviews","Portuguese","video","Dd42Tc38bTE"),
("Terry Crews Talks Acting, Suicidal Thoughts, Porn Addiction and Mental Health - The Mental Game","Celebrity Interviews","English","video","8dzKdPxwnP4"),
("Exclusive Interview with Terry Crews on Why He Quit Porn","Celebrity Interviews","English","video","tV6F1Mkh7B0"),

# ---------------- Dr. Trish Leigh ----------------
("Dr. Trish Leigh (channel)","Dr. Trish Leigh","English","channel","channel/UC2UjsmTlsL1IhqiRt2oKvXA"),
("Porn Brain Rewire 2022 (Quit Porn with Dr. Trish Leigh)","Dr. Trish Leigh","English","video","p9M7Yk6nB4Q"),
("Porn, Checking People Out, and Dopamine: Porn Rewire w/ Dr. Trish Leigh","Dr. Trish Leigh","English","video","pposQ0xTerU"),
("Porn Brain Rewire Program with Dr. Trish Leigh","Dr. Trish Leigh","English","video","U2HmfdXRjL0"),
("Dr. Trish Leigh Spills the TRUTH (Porn Brain Rewire)","Dr. Trish Leigh","English","video","rJwV4rT0W-w"),
("Porn Brain Rewire Strategies to Succeed (w/ Dr. Trish Leigh)","Dr. Trish Leigh","English","video","WHtbT-l4LAU"),
("Persist and Persevere on your Porn Brain Rewire (w/ Dr. Trish Leigh)","Dr. Trish Leigh","English","video","C_N3S8zACrM"),
("Porn Brain Rewire Strategies (w/ Dr. Trish Leigh)","Dr. Trish Leigh","English","video","t7vpKJUMylI"),
("5 (Easy) Ways to Replenish Dopamine on a Porn Brain Rewire (w/ Dr. Trish Leigh)","Dr. Trish Leigh","English","video","l9T2oumLN3s"),
("The Nightmare of Porn Addiction Podcast (w/ Dr. Trish Leigh)","Dr. Trish Leigh","English","video","zZuuN7wy1BQ"),

# ---------------- Dopamine detox ----------------
("How To Reset Your Mind? Dopamine Detox? How To Deal With Social Media Addiction?","Dopamine Detox","English","video","k0WDtwhTnOs"),
("DOPAMINE DETOX: How Alcohol, Porn & Social Media Is Making This Generation STRUGGLE | Scott Galloway","Dopamine Detox","English","video","jX82Bwc47N8"),
("7 Day Social Media Detox | Dopamine Reset","Dopamine Detox","English","video","8nPOaiKGO58"),
("How To Reset Your Brain's Pleasure Pathways And Overcome Porn Addiction","Dopamine Detox","English","video","etXJlW_8pQ4"),
("Dopamine Neuroscientist: 'Even A Little Bit Of Social Media, Netflix, Weed & Porn Does This To You!'","Dopamine Detox","English","video","OJIvoOal0hw"),
("How I Reset My Dopamine Levels (And You Can Too)","Dopamine Detox","English","video","Eh8o_wbnYXM"),
("Neuroscientist Reveals: THIS 60-Minute Rule Will FIX Your Dopamine Addiction","Dopamine Detox","English","video","d1e_Y88en3M"),
("How To Actually Dopamine Detox (Quitting Social Media)","Dopamine Detox","English","video","alPgPOI_Gac"),

# ---------------- 12-step ----------------
("Sexual Compulsives Anonymous (channel)","12-Step / Support Groups","English","channel","@SCA-Recovery"),
("Sex Addiction: Step One of the Twelve Steps | Dr. Doug Weiss","12-Step / Support Groups","English","video","GsZY9A51r6Q"),
("Twelve Step Support Groups for Sex Addiction | Dr. Doug Weiss","12-Step / Support Groups","English","video","czmJdRrygRM"),
("What to expect at a Sex Addicts Anonymous Meeting","12-Step / Support Groups","English","video","fWfHiv1bvPs"),
("Sex Addicts Recovery Podcast (playlist)","12-Step / Support Groups","English","playlist","PLn0dcZg-Ou7giI4YkXGXsBWDHJgtymw9q"),
("#104: The 12-Step Experience for Sex and Love Addicts","12-Step / Support Groups","English","video","uDtnHrAz9Nw"),
("My Journey Through Sexaholics Anonymous","12-Step / Support Groups","English","video","DljfJRU4YK4"),
("Withdrawal & Relapse In SAA Recovery - Sex Addicts Anonymous","12-Step / Support Groups","English","video","AC_gmmDgoAI"),
("Bay Area Sex Addicts Anonymous (channel)","12-Step / Support Groups","English","channel","@bayareasexaddictsanonymous1892"),
("Sex Addicts Anonymous","12-Step / Support Groups","English","video","2T_rXG0QUdo"),

# ---------------- Blockers / accountability ----------------
("Anti-Porn Software | Covenant Eyes Review (Can it help you?)","Blockers / Accountability Tools","English","video","WQfpfY8WipM"),
("Accountable2You Porn Blocking Accountability Software REVIEW","Blockers / Accountability Tools","English","video","gxtv9tMPDK4"),
("Ever Accountable (X3watch) Porn Blocking Accountability Software REVIEW","Blockers / Accountability Tools","English","video","ovFLSfAMDfs"),
("Is Covenant Eyes Enough for Porn Addiction? A Clinical Answer","Blockers / Accountability Tools","English","video","BRX1DdvO9xk"),
("Covenant Eyes Review - Is Accountability Software Right for You or Your Family?","Blockers / Accountability Tools","English","video","efzR1yyzIfs"),
("Covenant Eyes Reviewed by a Porn Addiction Coach (2022)","Blockers / Accountability Tools","English","video","59rB0QOEInk"),
("Is Covenant Eyes 'Shameware'?","Blockers / Accountability Tools","English","video","pDuZGAkMSYc"),
("Net Nanny Porn Blocking Accountability Software REVIEW","Blockers / Accountability Tools","English","video","2cEEGzv9DSo"),
("Covenant Eyes (channel)","Blockers / Accountability Tools","English","channel","covenanteyes"),
("Covenant Eyes Review | Why It DIDN'T Work for Me","Blockers / Accountability Tools","English","video","tqbFSWJL2DU"),

# ---------------- Hindi ----------------
("How To Quit Porn Addiction? - World's Best Motivational Video in Hindi","Hindi","Hindi","video","8XkomUM7hNM"),
("Porn Dekhna Kaise Chhode - How To Quit Porn Addiction And Bad Habits by Rajveer Singh","Hindi","Hindi","video","RviuaGS6l0Q"),
("Kaise Chhodo Porn Addiction - Sab Kuch Revealed! (Hindi/Urdu)","Hindi","Hindi / Urdu","video","d-rLBtFIvZ4"),
("Porn Addiction Kaise Chhode: Step-by-Step Guide | Porn Addiction Ka Ilaj","Hindi","Hindi","video","2Jjz76z6F_c"),
("How to stop addiction in Hindi | Addiction ko kaise chhode | Dr Kashika Jain","Hindi","Hindi","video","aJP28Sp9xRQ"),
("Porn addiction kaise chhode","Hindi","Hindi","video","t7Yv3K7zSiY"),
("How to quit porn addiction and bad habits? - Video in Hindi by Him-eesh","Hindi","Hindi","video","eAnW7c9YQJo"),
("Porn ki lat se chutkara | Porn Addiction | Bad Habits | Brahmacharya","Hindi","Hindi","video","793ydNmKYKM"),
("Porn Addiction Se Kaise Bache","Hindi","Hindi","short","CbzWdpjIFws"),

# ---------------- Spanish ----------------
("Adiccion al Sexo y a la Pornografia: Sintomas y Como Superarla","Spanish","Spanish","video","E3GmrBkkubg"),
("Como el Porno destruye tu Cerebro (y tu vida)","Spanish","Spanish","video","EerpJfNErsI"),
("Como Curar la Adiccion al Porno (Guia Definitiva)","Spanish","Spanish","video","VhNr73kkotk"),
("Como salir de la adiccion al p*rno PASO A PASO","Spanish","Spanish","video","ns5O9fR-wK0"),
("Como VENCER la PORNOGRAFIA! Claves para SUPERAR la ADICCION","Spanish","Spanish","video","s8Mrz73Z6A0"),
("Como DEJAR de ver PORNOGRAFIA | Guia Definitiva","Spanish","Spanish","video","NlILe3_kvug"),
("Adiccion A La Pornografia - COMO SUPERARLA, con el psicologo Miguel Zammer","Spanish","Spanish","video","SjW_mNIULbU"),
("Soy ADICTO al PORNO! Como SUPERAR la ADICCION a la PORNOGRAFIA!","Spanish","Spanish","video","37I-CvuVP_c"),
("Como superar la adiccion a la pornografia? | Antonio Nistal","Spanish","Spanish","video","ZbSBvPW2zxI"),
("Como Revertir los Efectos de la Pornografia en tu Cerebro","Spanish","Spanish","video","EVP1LcaoHog"),

# ---------------- Portuguese ----------------
("Como parar de assistir PORNOGRAFIA para SEMPRE!","Portuguese","Portuguese","video","plPU-ugKSX8"),
("Como LARGAR o VICIO em PORNOGRAFIA em 2024 (com Miguel Soriani)","Portuguese","Portuguese","video","hZ3aP92Rzxw"),
("VICIO em P*RN*GRAFIA: 5 Formas de PARAR AGORA","Portuguese","Portuguese","video","AZryT1rohlk"),
("COMO PARAR O VICIO NA PORNOGRAFIA","Portuguese","Portuguese","video","03N6qDbH1tM"),
("Vicio em Pornografia. Como Vencer?","Portuguese","Portuguese","video","nAHCRT74scc"),
("COMO PARAR COM O VICIO EM PORNOGRAFIA - Pablo","Portuguese","Portuguese","video","C95iriMgO_k"),
("CINCO ESTRATEGIAS PARA INTERROMPER OU QUEBRAR O CICLO VICIOSO DA PORNOGRAFIA!","Portuguese","Portuguese","video","zznuyiqFqC8"),
("Como superar o vicio em masturbacao e pornografia de uma vez por todas!","Portuguese","Portuguese","video","0X8Wu1KSt2k"),
("COMO VENCER O VICIO EM PORNOGRAFIA","Portuguese","Portuguese","video","O280vGDPuGA"),
("COMO e PORQUE se LIVRAR da PORNOGRAFIA (neurociencia)","Portuguese","Portuguese","video","eQ4ZD2oKufg"),

# ---------------- Motivation ----------------
("How To Stop Porn Addiction - Motivational Speech | Robert Kayanja Jr","Motivation","English","video","HqNXU0oQRVA"),
("How to Cure Porn Addiction? | Andrew Tate Motivational Speech","Motivation","English","video","rf0HbMDiFo4"),
("STOP wasting your LIFE - Take control instead (motivational speech)","Motivation","English","video","Mz3yCKa1mMA"),
("Motivation To Quit Porn (playlist)","Motivation","English","playlist","PL-6gbuzvSL3EuJu8KANbAlts2ry5SaWBs"),
("How To Cure P#RN ADDICTS? Andrew Tate Motivational Speech","Motivation","English","video","fY_FzBtIWdE"),
("STOP Looking For Motivation To QUIT PORN & REBOOT YOUR LIFE","Motivation","English","video","YXIh9HQRMdI"),

# ---------------- Podcasts ----------------
("Porn Addiction & Monastic Wisdom w/ Jeremy Lipkowitz | Ep 108 | Secondhand Therapy Podcast","Podcasts / Long-Form","English","video","EVEYdBHvvqo"),
("Overcoming Porn Addiction || Pheyland Barthen || Winning Conversations Podcast","Podcasts / Long-Form","English","video","PZjUbJzPjOs"),
("The Porn Reboot Podcast Episode 479: Maintenance Stage of Porn Addiction","Podcasts / Long-Form","English","video","gDqNMgQ5gc8"),
("Ep. 94: Porn addiction & men's mental health: Breaking the shame cycle (Jeremy Lipkowitz)","Podcasts / Long-Form","English","video","sOJCtlj0fJs"),
]

def url_for(kind, ident):
    if kind == "playlist":
        return "https://www.youtube.com/playlist?list=" + ident
    if kind == "short":
        return "https://www.youtube.com/shorts/" + ident
    if kind == "channel":
        return "https://www.youtube.com/" + ident
    return "https://www.youtube.com/watch?v=" + ident

def main(out):
    seen, rows = set(), []
    for title, cat, lang, kind, ident in ROWS:
        if ident in seen:
            print("dup skipped:", ident, title, file=sys.stderr)
            continue
        seen.add(ident)
        rows.append((title, cat, lang, kind, ident))

    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Title", "Category", "Language", "Type",
                    "URL", "Video / Playlist ID", "Watched?", "Rating", "Notes"])
        for i, (title, cat, lang, kind, ident) in enumerate(rows, 1):
            w.writerow([i, title, cat, lang, kind.capitalize(),
                        url_for(kind, ident), ident, "", "", ""])
    print(f"{len(rows)} rows -> {out}")
    cats = {}
    for _, c, _, _, _ in rows:
        cats[c] = cats.get(c, 0) + 1
    for c in sorted(cats, key=lambda k: -cats[k]):
        print(f"  {cats[c]:>3}  {c}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "porn_addiction_youtube_videos.csv")
