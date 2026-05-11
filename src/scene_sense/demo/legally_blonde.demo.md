# Legally Blonde — Demo Bundle (Final)

6 cards, ordered by on-screen timestamp. Cue points **manually verified** against the film. Each triggers at the precise moment where the prompt lands.

**Schema:**
- `sceneHRIT`: proactivePrompt · title · question · answer · followUps
- `sceneTrivia`: proactivePrompt · triviaText · triviaOptions · answerText · followUps
- `sceneFact`: proactivePrompt · factHeader · factText · sourceUrl · followUps
- `actorFact`: proactivePrompt · actorName · character · factText · followUps (chained w/ `nextFollowUps` for send-to-phone)
- `sceneCuepoint` carries `startTime` / `endTime` (the active 15–30s window), plus `sceneStart` / `sceneEnd` (full VLM scene span) and a `cueAnchor` note.

---

## 1 · sceneFact — Scene 1 · cue **00:01:33 – 00:02:03** (30s)

**Scene anchor:** Elle gets the sign with her name at 00:01:33 — her first clear on-screen beat, before trivia at 00:03:20.

- **Proactive prompt:** Elle Woods almost wasn't Reese
- **Headline (same as prompt):** Elle Woods almost wasn't Reese
- **Fact:** Christina Applegate passed on the role of Elle — she feared typecasting after *Married... With Children*. She later called turning it down a big f***ing mistake.
- **Source:** cinemablend.com

**Follow-ups:**
- **Why wasn't Reese the first choice?** *(USE in demo)* — MGM initially rejected her, fearing she was too similar to her intense character in *Election*. Director Robert Luketic knew she was Elle by page 5 of the script and fought to cast her.
- **Who else was considered?** — Gwyneth Paltrow, Charlize Theron, Alicia Silverstone, and Katherine Heigl were all on the shortlist. Producer Marc Platt briefly floated Britney Spears until writer Karen McCullah talked him out of it.

---

## 2 · sceneTrivia — Scene 2 · cue **00:03:20 – 00:03:37** (17s)

**Scene anchor:** Elle says *"Bruiser, what's this?"* at 00:03:20 — Bruiser clearly on screen with the card.

- **Proactive prompt:** What's Bruiser's real name?
- **Question:** What was the name of the dog actor who played Bruiser?

**Options:**
- ✅ Moonie
- Buddy
- Max
- Rocky

- **Answer:** Moonie was a rescue Chihuahua adopted by trainer Sue Chipperton. He lived to be 18.

**Follow-ups:**
- **What happened to Moonie?** — He passed away in March 2016 at age 18. Reese Witherspoon posted a tribute on Instagram calling him a sweet little Chihuahua who was very loved.
- **What were Moonie's other roles?** *(USE in demo)* — He lived and trained alongside Gidget, the original Taco Bell Chihuahua, and appeared in *Legally Blonde 2* and the TV series *Three Sisters*.

---

## 3 · sceneTrivia — Scene 7 · cue **00:10:23 – 00:10:43** (20s)

**Scene anchor:** Elle walking alongside Warner's car at ~00:10:23, before he drives off at 00:10:43 — car is clearly visible on screen with her.

- **Proactive prompt:** What's Warner's breakup ride?
- **Question:** As Warner drives Elle home after the breakup, what kind of car is he driving?

**Options:**
- ✅ 2000 Porsche Boxster (986)
- Porsche 911 Carrera (996)
- Porsche Cayenne
- BMW Z3 Roadster

- **Answer:** Warner drives a 2000 Porsche Boxster — Porsche's mid-engined roadster, introduced in 1996 as their entry-level model.

**Follow-ups:**
- **What does it cost today?** *(USE in demo)* — A new 2026 Boxster starts around $75,300. A used 2000 Boxster in good condition runs $10,000–$20,000, making it one of the most accessible Porsches.
- **Boxster vs 911?** — The Boxster is mid-engined with a folding soft top. The 911 is rear-engined, more powerful, and roughly double the price.

---

## 4 · actorFact — Scene 25 · cue **00:32:15 – 00:32:45** (30s)

**Scene anchor:** Paulette (Jennifer Coolidge) clearly on screen at 00:32:15 — prime "Recognize her?" moment.

- **Proactive prompt:** Recognize her?
- **Actor:** Jennifer Coolidge
- **Character:** Paulette
- **Fact:** Jennifer Coolidge waited tables alongside Sandra Bullock before her first big break as Stifler's Mom in *American Pie* (1999).

**Follow-ups (chained, two-button at each layer, send-to-phone QR at the Emmy layer):**

**▸ Her first Emmy win**
*The White Lotus* (2022). She played Tanya McQuoid — a role that won her two consecutive Primetime Emmys and a Golden Globe.

&nbsp;&nbsp;**B1 ▸ See her upcoming projects**
&nbsp;&nbsp;A Minecraft Movie (2025) as Vice Principal Marlene · Riff Raff (dark comedy, star-studded cast) · voice role as Pierre the Pigeon-Hawk · Legally Blonde 3 reprising Paulette.

&nbsp;&nbsp;&nbsp;&nbsp;**B1 ▸ Latest on Legally Blonde 3** *(USE in demo)*
&nbsp;&nbsp;&nbsp;&nbsp;Still in active development as of May 2026. No theatrical release date set, but Reese Witherspoon confirmed the threequel is absolutely still happening.

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**▸ Will Bruiser return in Legally Blonde 3?**
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;No confirmation yet. The original Bruiser (Moonie) passed away in 2016, so any return would be a new Chihuahua stepping into the role — likely cast close to production.

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**▸ Who else from the original cast will return?**
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Reese Witherspoon is producing and reprising Elle. Jennifer Coolidge is confirmed back as Paulette. No formal announcements yet on Luke Wilson (Emmett), Selma Blair (Vivian), or Matthew Davis (Warner).

&nbsp;&nbsp;&nbsp;&nbsp;**B2 ▸ Cast of Riff Raff** *(visible, not walked in demo)*
&nbsp;&nbsp;&nbsp;&nbsp;Stars Jennifer Coolidge alongside Ed Harris, Lewis Pullman, Pete Davidson, and Bill Murray. Directed by Dito Montiel — a darkly comedic family crime story.

&nbsp;&nbsp;**B2 ▸ Send this to my phone** 📲
&nbsp;&nbsp;QR handoff — continue exploring Coolidge's upcoming projects and Legally Blonde 3 updates on your phone.

---

## 5 · sceneHRIT — Scene 38 · cue **00:46:46 – 00:47:16** (30s)

**Scene anchor:** Paulette says *"I'm taking the dog, dumbass!"* at 00:46:46, right after Elle's legal-jargon bluff at 00:46:09 with *"habeas corpus."*

- **Proactive prompt:** Fact Check: Habeas Corpus?
- **Title = Question:** Could Elle really use habeas corpus to get the dog back?
- **Answer:** Pure Hollywood bluff. Habeas corpus is a writ to produce a detained person before a court — it has nothing to do with pets. The correct legal action for recovering a dog is a writ of replevin.

**Follow-ups (two buttons — selected question becomes the title of the next turn):**
- **Would her bluff actually work?** *(USE in demo)* — The tactic is real — lawyers call it dropping jargon on a non-lawyer to close out a dispute before it reaches court. Elle's version is just unusually fast.
- **What's a writ of replevin?** — The actual legal tool Elle should have named. It's a civil action to recover personal property someone is wrongfully holding — dogs, cars, jewelry. The court can order the property returned before the full lawsuit is decided.

---

## 6 · sceneHRIT — Scene 67 · cue **01:21:35 – 01:22:05** (30s)

**Scene anchor:** Judge says *"proceed"* at 01:21:35, right after Elle cites Mass. Rule 3:03 and Emmett agrees to supervise. Brooke fired Callahan at 01:20:06.

- **Proactive prompt:** Fact Check: Elle takes over?
- **Title = Question:** Could Elle actually take over as lead counsel?
- **Answer:** Pure Hollywood magic. A real judge would have denied the motion instantly, noted Elle's lack of qualifications, and granted Brooke a continuance to find a new, licensed attorney.

**Follow-ups:**
- **Can law students really represent clients?** *(USE in demo)* — Under Rule 3:03. Michelle Obama, Loretta Lynch, and Justice William Brennan all practiced under it at the Harvard Legal Aid Bureau — the oldest student-run legal services office in the US, founded in 1913.
- **What's Emmett's role as supervising attorney?** — Under Rule 3:03, the supervisor has to be physically in court and takes full professional responsibility. If Elle had blown the defense, Emmett's license would have been on the line.

---

## Card summary (in playback order)

| # | Shape | Scene | Cue point | Duration | Proactive prompt |
|---|---|---|---|---|---|
| 1 | sceneFact | 1 | 00:01:33 – 00:02:03 | 30s | Elle Woods almost wasn't Reese |
| 2 | sceneTrivia | 2 | 00:03:20 – 00:03:37 | 17s | What's Bruiser's real name? |
| 3 | sceneTrivia | 7 | 00:10:23 – 00:10:43 | 20s | What's Warner's breakup ride? |
| 4 | actorFact | 25 | 00:32:15 – 00:32:45 | 30s | Recognize her? |
| 5 | sceneHRIT | 38 | 00:46:46 – 00:47:16 | 30s | Fact Check: Habeas Corpus? |
| 6 | sceneHRIT | 67 | 01:21:35 – 01:22:05 | 30s | Fact Check: Elle takes over? |

---

## Verification notes

- All 6 cue points manually verified against the film by Rahul.
- `sceneCuepoint.startTime` / `endTime` = the active trigger window (17–30s).
- `sceneCuepoint.sceneStart` / `sceneEnd` = the full VLM scene span (for reference).
- `sceneCuepoint.cueAnchor` = plain-English note of what's happening at the trigger moment.
- JSON validated — 6 cards, ordered by timestamp, valid schema.
- Files: `data/outputs/legally_blonde.demo.json` + `docs/research/lb_demo_final.md` + `docs/research/lb_demo_ux_walkthrough.md`.
