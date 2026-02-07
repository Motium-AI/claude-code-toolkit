---
name: audiobook
description: Transform technical documents into long-form audiobooks. Uses 4-agent heavy analysis, TTS optimization, Michael Caine oration style, and stop-slop enforcement. Use when asked to "create an audiobook", "turn this into audio", or "/audiobook".
---

# Audiobook Creation Skill

Transform technical documents into compelling, TTS-optimized audiobooks using multi-agent analysis and narrative synthesis.

## Input

$ARGUMENTS

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: CONTENT DISCOVERY                                     │
│     └─► Identify source documents                               │
│     └─► Read and analyze each document                          │
│     └─► Identify overlapping themes and unique insights         │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: HEAVY ANALYSIS (4 Parallel Opus Agents)               │
│     └─► First Principles: Core insights, deletion candidates    │
│     └─► AGI-Pilled: Narrative structure, central metaphor       │
│     └─► TTS Production Expert: Audio constraints, formatting    │
│     └─► Stop-Slop Expert: AI pattern watchlist, voice traps     │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: SYNTHESIS                                             │
│     └─► Resolve tradeoffs between agent recommendations         │
│     └─► Define chapter structure with word counts               │
│     └─► Establish production rules (format, TTS, stop-slop)     │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: WRITING                                               │
│     └─► Write preamble (90 words, topic + tone + preview)       │
│     └─► Write all chapters as continuous prose                  │
│     └─► Apply stop-slop watchlist pass                          │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 5: QUALITY ASSURANCE                                     │
│     └─► Self-score against 5 dimensions (target 40+/50)         │
│     └─► Output single MD file optimized for TTS                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Content Discovery

### Step 1.1: Identify Source Documents

Parse the user's request to identify:
- Source documents (paths or descriptions)
- Desired voice/style (default: Michael Caine oration style)
- Target length (default: 7,000-10,000 words)
- Output filename

### Step 1.2: Read and Analyze Sources

For each source document:
1. Read the full content
2. Identify key themes, insights, and narrative threads
3. Note overlapping content between documents
4. Flag unique insights that must not be lost in synthesis

---

## Phase 2: Heavy Analysis (4 Parallel Agents)

**CRITICAL**: Launch ALL 4 agents in a SINGLE message with multiple Task tool calls. This makes them run in parallel.

> **Architecture: Task() (not TeamCreate)** — Agents produce independent analysis artifacts (core insights, narrative structure, TTS constraints, slop watchlist). Coordinator synthesizes tradeoffs in Phase 3.

### Agent 1: First Principles Analysis

```
Task(
  subagent_type="general-purpose",
  description="First Principles Analysis",
  model="opus",
  prompt="""You are distilling source documents into core audiobook insights.

Apply the Elon Musk algorithm:
1. **Question every theme** - Why does this need to be in the audiobook?
2. **Delete** - Remove anything redundant, tangential, or dilutive
3. **Simplify** - Merge overlapping concepts into singular, powerful statements
4. **Sequence** - What's the most compelling order for the listener?

SOURCE DOCUMENTS:
[PASTE SUMMARIES OF SOURCE DOCUMENTS]

## Your Mission

From an audiobook perspective:
- Which themes are ESSENTIAL vs. nice-to-have?
- What content overlaps and can be merged?
- What order creates the best narrative tension?
- What's the single most compelling insight to open with?
- What's the satisfying conclusion that ties everything together?

## Output

1. **10 Core Insights** (ranked by importance)
2. **Deletion List** (content that weakens the narrative)
3. **Proposed Narrative Arc** (beginning → middle → end)
4. **Central Hook** (the 1-sentence premise that grabs attention)
"""
)
```

### Agent 2: AGI-Pilled Analysis

```
Task(
  subagent_type="general-purpose",
  description="AGI-Pilled Analysis",
  model="opus",
  prompt="""You are designing the MOST COMPELLING audiobook possible from this material.

**Core beliefs:**
- Listeners are intelligent - don't condescend
- Emotion drives retention more than information
- One transforming metaphor beats five scattered ones
- The best audiobooks feel like conversations, not lectures
- Every chapter should leave the listener wanting the next

SOURCE DOCUMENTS:
[PASTE SUMMARIES OF SOURCE DOCUMENTS]

## Your Mission

Design the audiobook structure:
1. **Central Metaphor**: One image that transforms across chapters
2. **Emotional Arc**: What does the listener FEEL at each stage?
3. **Chapter Outline**: 7-12 chapters with evocative titles
4. **Meta-awareness**: Where can the narrative acknowledge itself?
5. **Recurring Anchors**: What motifs appear 3+ times with deepening meaning?

## Narrative Techniques to Consider

- **Frame narrative**: The narrator has a stake in the story
- **Temporal fracture**: Break chronology for dramatic effect
- **Bleeding meta-awareness**: Hint at revelations before confirming
- **Deletion litany**: Lists read with rhythmic relish
- **Quiet endings**: Not every chapter needs a punchline

## Output

- **Proposed Title** (evocative, not descriptive)
- **Central Metaphor** and how it transforms across chapters
- **Chapter Outline** with emotional beats for each
- **3 Recurring Anchors** with their appearance schedule
"""
)
```

### Agent 3: TTS Production Expert

```
Task(
  subagent_type="general-purpose",
  description="TTS Audio Production Expert perspective",
  model="opus",
  prompt="""You are a TTS audio production expert optimizing this audiobook for text-to-speech engines.

SOURCE DOCUMENTS:
[PASTE SUMMARIES OF SOURCE DOCUMENTS]

## TTS Constraints You Must Address

**Length & Pacing:**
- 800-1,200 words per chapter (ceiling 1,500)
- 90-word preamble before chapter 1 (topic, tone, what to expect)
- Total target: 7,000-10,000 words

**Number Handling:**
- One number per sentence, two max if directly compared
- Spell out numbers under 10, use digits for larger
- Avoid percentages in rapid succession

**Technical Content:**
- No file paths - give everything human names
- No code blocks or technical syntax
- No markdown that TTS will read aloud (# becomes "hashtag")

**Punctuation for Pauses:**
- Blank lines between paragraphs = short pause
- `--` for Caine-style asides = medium pause
- Three blank lines between chapters = longer pause (TTS engines pause on whitespace)
- No semicolons (awkward TTS pause)
- No parentheses (use dashes instead)
- NEVER use `[PAUSE]` or similar markers - TTS will read them aloud

**Natural Flow:**
- Contractions always (it's, don't, won't - not it is, do not)
- Parenthetical asides under 8 words
- Groups of items: max 3 named, then summarize
- Shorthand names after first introduction

## Output

1. **Production Spec** (word counts per chapter, preamble requirements)
2. **Formatting Rules** (how to handle pauses, numbers, technical terms)
3. **TTS Anti-patterns** (specific constructs that TTS handles poorly)
4. **Sample Preamble** (90 words demonstrating the format)
"""
)
```

### Agent 4: Stop-Slop Expert

```
Task(
  subagent_type="general-purpose",
  description="Stop-Slop Enforcement Expert review",
  model="opus",
  prompt="""You are a stop-slop enforcement expert. Your mission: eliminate predictable AI writing patterns from the audiobook.

SOURCE DOCUMENTS:
[PASTE SUMMARIES OF SOURCE DOCUMENTS]

## Stop-Slop Core Rules

1. **Cut filler phrases** - Remove throat-clearing openers and emphasis crutches
2. **Break formulaic structures** - Avoid binary contrasts, dramatic fragmentation, rhetorical setups
3. **Vary rhythm** - Mix sentence lengths. Two items beat three.
4. **Trust readers** - State facts directly. Skip softening, justification, hand-holding.
5. **Cut quotables** - If it sounds like a pull-quote, rewrite it.

## Your Mission

Create a comprehensive watchlist for THIS specific audiobook:

### Content Traps
- AI-typical transitions and openers
- Overused emphasis phrases
- Generic profundity markers

### Voice Traps
- Wisdom-dispenser constructions ("X isn't about Y. It's about Z.")
- Anthropomorphism treadmill (agents "wrestle," "grapple," "confront")
- Caine-voice parody risks ("Not a lot of people know that" echoes)

### Structural Traps
- Binary contrast reveals ("Not X. Y.") - max once per book
- Orphan dramatic fragments ("Gone." "Nothing." "Zero.")
- Three-item lists (two items beat three)
- Punchy closers on every chapter (vary: some end quietly)
- Recap tax (orient through new material, not summaries)

## Output

1. **35-Item Watchlist** (specific phrases and patterns to avoid)
2. **Voice Traps** (patterns that undermine the Caine voice)
3. **Structural Traps** (patterns that make structure predictable)
4. **Scoring Rubric** (5 dimensions, 10 points each, target 40+/50)
"""
)
```

---

## Phase 3: Synthesis

After all 4 agents return, synthesize their outputs:

### 3.1 Resolve Tradeoffs

For each tension between agents, document:
```
TRADEOFF: [topic]
- Agent X says: [position] because [reasoning]
- Agent Y says: [position] because [reasoning]
- Resolution: [chosen approach with rationale]
```

Common tradeoffs:
- **Title style**: Markdown headings vs. plain prose (prefer plain prose for TTS)
- **Meta-narrative placement**: Confined to one chapter vs. bleeding throughout
- **Chronology**: Strict order vs. temporal fracture for dramatic effect
- **Metaphor count**: Multiple metaphors vs. one that transforms

### 3.2 Define Chapter Structure

Create a table:
| Chapter | Title | Word Count | Emotional Beat | Key Content |
|---------|-------|------------|----------------|-------------|
| Preamble | - | 90 | Invitation | Topic, tone, preview |
| 1 | "..." | 800-1,200 | Hook | Opening insight |
| ... | ... | ... | ... | ... |

### 3.3 Establish Production Rules

Document final rules for:
- **Format**: Title style, pause markers, paragraph spacing
- **TTS**: Number handling, technical terms, contractions
- **Stop-slop**: Top 15 patterns to avoid during writing

---

## Phase 4: Writing

### 4.1 Write Preamble (90 words)

The preamble must:
- State the topic without spoiling insights
- Set the tone (reflective, conversational, surprising)
- Preview what the listener will experience
- NOT include: "In this audiobook," "We will explore," or similar meta-framing

### 4.2 Write Chapters

For each chapter:
1. Open with the chapter title as plain prose on its own line
2. Write continuous prose (no subheadings)
3. Honor the emotional beat for this chapter
4. Apply TTS constraints throughout
5. End with three blank lines (creates natural pause in TTS)

### 4.3 Apply Stop-Slop Pass

After writing, scan for and eliminate:
- Every item on the 35-item watchlist
- Voice traps specific to the chosen narrator style
- Structural predictability (vary endings, avoid binary reveals)

---

## Phase 5: Quality Assurance

### 5.1 Self-Score (Target: 40+/50)

| Dimension | Question | Score |
|-----------|----------|-------|
| **Directness** (1-10) | Can you delete the first sentence of any paragraph without loss? | |
| **Rhythm** (1-10) | Sentence-length standard deviation above 4 words? | |
| **Trust** (1-10) | Count evaluative adjectives (profound, elegant, devastating). Each costs 0.5 points. | |
| **Authenticity** (1-10) | Would a blind reader guess AI or human? | |
| **Density** (1-10) | Fewer than 8 distinct points per 1,000 words = too dilute. | |

**If score < 40**: Revise weak dimensions before outputting.

### 5.2 Output

Write the final audiobook to a single MD file:
- Plain prose throughout (no markdown syntax that TTS will read)
- Three blank lines between chapters (creates natural pause)
- `--` for Caine-style asides
- Blank lines between paragraphs
- NEVER use `[PAUSE]` or similar text markers - TTS reads them aloud

---

## Voice Guide: Michael Caine Style

**The Caine voice is:**
- Conversational, not lecturing
- Uses contractions naturally (it's, don't, won't)
- Employs asides with dashes -- like this, you see --
- Builds to points through stories, not announcements
- Occasionally pauses mid-thought to reflect
- Never condescends, treats listener as intelligent
- Underplays revelations (lets facts speak)

**Caine voice traps to avoid:**
- Over-using "you see" or "the thing is"
- Echoing his famous lines ("Not a lot of people know that")
- Forced Cockney rhythms
- Explaining jokes or metaphors

**Sample Caine rhythm:**
> I spent twenty-five minutes reading the same paragraph. Not because it was difficult -- it wasn't. Because somewhere between the third and fourth reading, I forgot I'd read it at all. My notes said "confidence: high." They also said nothing useful.

---

## Stop-Slop Reference: Top 35 Patterns

### Filler Phrases (Cut These)
1. "Here's the thing" / "The reality is" / "Let's be clear"
2. "Let that sink in" / "Think about that"
3. "At the end of the day"
4. "It's worth noting that"
5. "Interestingly enough"
6. "Needless to say"
7. "In other words"
8. "Simply put" / "Put simply"
9. "The fact of the matter is"
10. "It goes without saying"

### Profundity Markers (Rewrite These)
11. "ever-evolving landscape"
12. "profound implications"
13. "game-changer" / "paradigm shift"
14. "raises important questions"
15. "And that changes everything"
16. "transformative impact"
17. "at its core"
18. "fundamentally"

### Structural Tells (Vary These)
19. "Not X. Y." binary contrast reveals (max 1x per book)
20. Orphan dramatic fragments ("Gone." "Nothing." "Zero.")
21. Three-item lists (two items beat three)
22. Em-dash before a reveal
23. Punchy one-liner chapter endings
24. "Actually" as reveal signal
25. Recap paragraphs at section starts

### Voice Traps (Avoid These)
26. Wisdom-dispenser: "Memory isn't about X. It's about Y."
27. Anthropomorphism treadmill: agents "wrestle," "grapple," "confront"
28. Aside inflation (max 2 dashes per 250 words)
29. Explaining metaphors after deploying them
30. Rhetorical questions that you immediately answer

### Flow Killers (Eliminate These)
31. Consecutive sentences of matching length (break one)
32. Paragraph starting with "But" after "And" paragraph
33. "In fact" as intensifier
34. "Of course" as dismissive cushion
35. "Perhaps" / "Maybe" hedging without purpose

---

## Example Output Structure

```
This is an audiobook about [topic]. For the next [duration], we'll [approach].
The voice you're hearing -- or imagining, if you're reading -- belongs to
[framing]. By the end, you'll understand [promise without spoiling].



Four Hundred and Seventy-Three Lines

I spent twenty-five minutes reading the same paragraph...



The Parliament of Minds

Twenty-four agents were asked a question...



...



The Bridge

Memory, it turns out, is not about storage...

The notebook is still open on my desk. I don't remember writing this.
```

Note: Three blank lines between chapters create natural pauses in TTS engines.

---

## Triggers

- `/audiobook`
- "create an audiobook"
- "turn this into audio"
- "make this TTS-ready"
- "audiobook from documents"
