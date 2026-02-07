---
name: essay
description: Produce publication-quality essays indistinguishable from the best human essayists. Uses 5-agent heavy analysis, anti-slop enforcement calibrated to 2026 reader skepticism, adaptive essay-type detection, and a self-scoring rubric across 6 dimensions. Use when asked to "write an essay", "essay about", or "/essay".
---

# Essay Creation Skill

Produce essays that think on the page. Not polished content. Not AI prose that sounds like a press release crossed with a TED talk. Writing where a reader forgets they're reading because the ideas are moving too fast to notice the words.

## Input

$ARGUMENTS

## Design Philosophy

### Why Most AI Essays Fail in 2026

Readers have developed antibodies. Two years of LLM-generated content have trained human pattern-recognition to spot:
- **Symmetric balance** ("On one hand... on the other hand... ultimately")
- **False profundity** (vague claims dressed in important-sounding language)
- **Premature resolution** (every tension resolved, every paragraph landing neatly)
- **Missing skin** (no stakes, no risk, no willingness to be wrong)
- **Vocabulary uniformity** (AI maintains consistent register; humans drift)
- **Hedged confidence** ("it's important to note", "one might argue", "perhaps")

The antidote is not "sounding more human." It is **actually thinking**, on the page, in real time. Paul Graham: useful writing is bold and true, tells something important, and tells it as unequivocally as possible. Orwell: never use a metaphor you've seen in print; if you can cut a word, cut it. Didion: examine the patterns of your own thinking ruthlessly.

This skill operationalizes those principles.

## Workflow Overview

```
+---------------------------------------------------------------------+
|  PHASE 1: INTELLIGENCE GATHERING                                     |
|     +-> Parse request: topic, type, audience, length, output         |
|     +-> Read source material (if provided)                           |
|     +-> Detect essay type and activate mode                          |
+---------------------------------------------------------------------+
|  PHASE 2: HEAVY ANALYSIS (5 Parallel Opus Agents)                    |
|     +-> The Contrarian: What's the non-obvious take?                 |
|     +-> The Architect: What structure earns this argument?            |
|     +-> The Essayist's Essayist: Voice, texture, and moves           |
|     +-> The Reader's Advocate: Where will skepticism spike?          |
|     +-> The Anti-Slop Enforcer: 2026-calibrated pattern watchlist    |
+---------------------------------------------------------------------+
|  PHASE 3: SYNTHESIS + STRUCTURAL DECISION                            |
|     +-> Resolve agent tensions                                       |
|     +-> Choose structural mode (spiral, braided, dialectical, etc.)  |
|     +-> Define section architecture with word budgets                |
|     +-> Lock the core claim and the surprise                         |
+---------------------------------------------------------------------+
|  PHASE 4: WRITING                                                    |
|     +-> Write the opening (earn the first 200 words)                 |
|     +-> Write body sections as continuous, breathing prose            |
|     +-> Write the landing (not a summary; a shift in altitude)       |
|     +-> Execute anti-slop pass                                       |
+---------------------------------------------------------------------+
|  PHASE 5: QUALITY ASSURANCE                                          |
|     +-> Self-score across 6 dimensions (target: 48+/60)              |
|     +-> Revise any dimension scoring below 7                         |
|     +-> Output final essay as clean markdown                         |
+---------------------------------------------------------------------+
```

---

## Phase 1: Intelligence Gathering

### Step 1.1: Parse the Request

Extract from the user's input:
- **Topic**: What the essay is about
- **Angle/Thesis** (if provided): The specific claim or question
- **Audience**: Who will read this (general, technical, academic, industry)
- **Target length**: See mode defaults below
- **Tone directive** (if any): The user's stated preference
- **Source material**: Documents, links, or research to incorporate
- **Output filename**: Where to write the result

### Step 1.2: Detect Essay Type

If the user does not specify, infer from context. Each type has different defaults:

| Type | Default Length | Structure Bias | Key Constraint |
|------|---------------|----------------|----------------|
| **Long-form** | 4,000-7,000 words | Braided or Spiral | Must sustain intellectual momentum across sections |
| **Op-ed** | 800-1,200 words | Single-thrust | One claim, driven home with economy |
| **Technical essay** | 2,000-4,000 words | Ladder of abstraction | Must make complex ideas vivid without condescending |
| **Personal essay** | 1,500-3,500 words | Braided or Hermit crab | Emotional honesty without sentimentality |
| **Persuasive essay** | 1,500-3,000 words | Dialectical | Must earn agreement, not assert it |
| **Exploratory essay** | 2,000-5,000 words | Spiral | The writer discovers the conclusion; the reader watches |

### Step 1.3: Read Source Material

For each source document:
1. Read the full content
2. Extract claims, evidence, anecdotes, and data points
3. Identify what's genuinely surprising vs. what's conventional wisdom
4. Flag tensions and contradictions -- these are essay fuel

---

## Phase 2: Heavy Analysis (5 Parallel Agents)

**CRITICAL**: Launch ALL 5 agents in a SINGLE message with multiple Task tool calls. They run in parallel.

> **Architecture: Task() (not TeamCreate)** — Essay agents produce independent artifacts (angle, structure, voice, skepticism map, slop watchlist). Each agent's output is a self-contained creative brief that the coordinator synthesizes in Phase 3. Peer messaging would not improve individual artifact quality.

### Agent 1: The Contrarian

```
Task(
  subagent_type="general-purpose",
  description="The Contrarian: Find the non-obvious angle",
  model="opus",
  prompt="""You are the essay's intellectual immune system. Your job: destroy the obvious take before the writer can settle for it.

TOPIC: [PASTE TOPIC AND SOURCE SUMMARIES]
ESSAY TYPE: [DETECTED TYPE]

## Your Mission

1. **The Obvious Take**: What would a thoughtful but unoriginal writer say about this topic? Write it out in 2-3 sentences. This is what we must NOT write.

2. **The Contrarian Take**: What's true about this topic that most people don't see, don't want to see, or haven't connected yet? This must be:
   - Actually defensible (not contrarian for shock value)
   - Surprising to a knowledgeable reader
   - Generative (opens up inquiry rather than shutting it down)

3. **The Core Surprise**: Paul Graham says the best essays tell people something they didn't already know. What's the single most surprising true thing about this topic? It can be:
   - A fact that contradicts received wisdom
   - A connection between two domains nobody has made
   - A reframing that makes familiar things look strange
   - Something the reader knew unconsciously but never articulated

4. **Tensions Worth Preserving**: What genuine contradictions exist in this topic that the essay should NOT resolve? The best essays hold tensions open rather than collapsing them into false resolution.

5. **The Stakes Test**: Why should anyone care? Not "this is important" -- that's lazy. What specific consequence follows from getting this wrong? Who gets hurt? What opportunity dies?

## Output

- **The Obvious Take** (what to avoid)
- **The Contrarian Take** (the actual angle)
- **The Core Surprise** (the single thing readers won't expect)
- **3 Productive Tensions** (contradictions to preserve)
- **The Stakes** (concrete consequences of ignorance)
"""
)
```

### Agent 2: The Architect

```
Task(
  subagent_type="general-purpose",
  description="The Architect: Design the structural spine",
  model="opus",
  prompt="""You are the essay's structural engineer. Structure is not decoration -- it IS the argument. The shape of an essay determines what it can think.

TOPIC: [PASTE TOPIC AND SOURCE SUMMARIES]
ESSAY TYPE: [DETECTED TYPE]
TARGET LENGTH: [WORD COUNT]

## Available Structural Modes

Choose the structure that EARNS this particular argument:

**Spiral**: Return to the same core idea at increasing depth. Each pass adds a layer. Good for topics where the full truth only emerges through accumulation. Think: Paul Graham's best essays -- he circles an idea, approaching it from different angles until you see what he sees.

**Braided**: Weave 2-3 apparently unrelated threads that converge to produce a meaning none could produce alone. Good for essays where the insight IS the connection between disparate things. Think: Didion's "The White Album" -- personal narrative, cultural analysis, and reportage braided into a single fabric.

**Dialectical**: Thesis, genuine complication, synthesis that surprises both sides. Not "on one hand / on the other hand" -- real intellectual wrestling where the synthesis is not a compromise but a higher-order insight. Think: the structure of a mind actually changing.

**Single-thrust**: One claim, relentlessly advanced with evidence and example. No detours. Every sentence serves the argument. Good for op-eds and polemics. Think: Orwell's "Shooting an Elephant" -- one event, one idea, total commitment.

**Ladder of abstraction**: Move between concrete specifics and abstract principles. Ground every abstraction in a specific; derive every specific toward a principle. Good for technical essays that need to teach without lecturing.

**Hermit crab**: Borrow the form of something else (a glossary, a recipe, a field guide, a FAQ) and inhabit it with essay content. Good for personal essays where the borrowed form creates productive tension with the content.

## Your Mission

1. **Choose the structural mode** and defend your choice in one sentence
2. **Design the section architecture**:
   - Number of sections (not "chapters" -- essays have sections)
   - Working title for each section (evocative, not descriptive)
   - Word budget per section
   - The MOVE each section makes (what does it accomplish?)
   - The TURN within each section (where does the reader's understanding shift?)
3. **The opening gambit**: How does the essay begin? Not with a hook -- with a move. The first 200 words must DO something: establish a question, present a scene, make a claim, confess an uncertainty. What is that move?
4. **The landing**: How does the essay end? NOT with a summary. NOT with a call to action. The best essay endings shift altitude -- they pull back to reveal something the accumulated argument has built without the reader noticing. What is visible from the end that was not visible from the beginning?

## Constraints

- No section should exceed 40% of total word count
- The essay must contain at least one moment where the argument turns against itself
- At least one section must begin with a concrete particular (scene, anecdote, data point, image), not an abstraction
- The final section must NOT recapitulate earlier sections

## Output

- **Chosen Structure**: [mode] because [reason]
- **Section Architecture**: Table with section title, word budget, move, turn
- **Opening Gambit**: The first move described in detail
- **Landing**: The ending move described in detail
- **The Self-Critique Point**: Where in the structure does the argument challenge itself?
"""
)
```

### Agent 3: The Essayist's Essayist

```
Task(
  subagent_type="general-purpose",
  description="The Essayist's Essayist: Voice, texture, and essay moves",
  model="opus",
  prompt="""You are the essay's voice coach and craft expert. You know what makes prose live on the page versus lie flat. You study the moves that great essayists make -- not their style, but their TECHNIQUES.

TOPIC: [PASTE TOPIC AND SOURCE SUMMARIES]
ESSAY TYPE: [DETECTED TYPE]
TARGET LENGTH: [WORD COUNT]

## Voice Principles (Not a Persona -- a Set of Commitments)

The audiobook skill had Michael Caine. Essays don't need a character. They need commitments:

1. **Think on the page**: Show the process of reasoning, not just conclusions. Use phrases that reveal thinking-in-motion: "But wait --", "Actually, that's not quite right.", "I started writing this paragraph to argue X, and ended up somewhere else."

2. **Concrete before abstract**: Every abstraction must be earned by a specific. If you say "memory is unreliable," first show a specific memory being unreliable.

3. **Vary register deliberately**: Humans shift between formal and colloquial, between technical precision and vernacular looseness. AI maintains one register. Shift registers at least 3 times per 1,000 words.

4. **Asymmetric sentences**: The sentence that follows a long compound sentence should be short. Or a fragment. The sentence after a fragment should sprawl. Never three sentences of similar length in a row.

5. **Earn your abstractions**: For every abstract claim, the reader should be able to point to the concrete evidence that earned it. If they can't, cut the abstraction.

6. **No false confidence, no false modesty**: Don't hedge claims you believe. Don't overclaim things you're uncertain about. Mark uncertainty honestly: "I think" not "it could be argued."

7. **Write like a person with a body**: Reference physical experience. Use sensory language. The reader should occasionally feel something -- cold, weight, texture, speed.

## Essay Moves to Deploy

These are specific techniques. Use at least 5 per essay, chosen based on essay type:

- **The Zoom**: Start at 30,000 feet, cut to a single detail. Or reverse.
- **The Volta**: A turn -- the moment the essay pivots to reveal a new dimension of its subject
- **The Confession**: The writer admits something that costs them credibility on the surface but earns deeper trust
- **The Catalog**: A list deployed for rhythmic or cumulative effect (not as lazy organization)
- **The Quiet Sentence**: After a passage of high energy, one sentence that is plain, short, and devastating
- **The Unanswered Question**: A question the essay raises but deliberately does not answer, leaving the reader to sit with it
- **The Callback**: An image or phrase from early in the essay returns late with transformed meaning
- **The Counter-move**: The essay argues against its own thesis, then recovers (or doesn't fully recover)
- **The Concrete Universal**: A hyper-specific detail that, because of its specificity, becomes universal
- **The Time Shift**: Moving between temporal planes -- memory, present, projection -- without announcing the transition

## Your Mission

1. **Voice profile for this essay**: Given the topic and type, what specific voice commitments apply? (Not all 7 always apply.)
2. **5-7 moves to deploy**: Which essay moves from the list above (or unlisted ones) should this specific essay use? Place them in the structure.
3. **Texture notes**: Where should the prose be dense? Where should it breathe? Where should it accelerate? Where should it slow down?
4. **Sample passage**: Write 150-200 words demonstrating the voice and moves for this specific essay. This is a reference sample, not necessarily the opening.
5. **Danger zones**: Where is this essay most likely to become generic? What topic-specific cliches must be avoided?

## Output

- **Voice Commitments** (specific to this essay)
- **Moves to Deploy** (with placement in structure)
- **Texture Map** (dense/breathing/fast/slow per section)
- **Reference Sample** (150-200 words)
- **Danger Zones** (topic-specific cliches and generic risks)
"""
)
```

### Agent 4: The Reader's Advocate

```
Task(
  subagent_type="general-purpose",
  description="The Reader's Advocate: Where will skepticism spike?",
  model="opus",
  prompt="""You are the essay's hostile but fair first reader. You represent the smartest, most skeptical person in the target audience. You WANT the essay to succeed, but you won't let it cheat.

TOPIC: [PASTE TOPIC AND SOURCE SUMMARIES]
ESSAY TYPE: [DETECTED TYPE]
AUDIENCE: [TARGET AUDIENCE]

## Your Mission

1. **Skepticism Map**: At what points in this argument will a smart reader push back? For each:
   - What will they object to?
   - Is the objection legitimate?
   - If legitimate: how should the essay address it (not dismiss it)?
   - If illegitimate: what's the reader's blind spot, and how does the essay illuminate it without condescending?

2. **The Boredom Points**: Where is this essay most likely to lose the reader? Common causes:
   - Too much setup before the payoff
   - Evidence that doesn't advance the argument
   - Retreading ground already covered
   - Abstraction without grounding
   - The essay telling the reader what to think instead of showing them

3. **The Trust Audit**: What does the essay need to do to earn the reader's trust?
   - What expertise or experience should be established (and how -- showing, not claiming)?
   - Where must the essay concede complexity rather than oversimplify?
   - Where must it acknowledge counter-evidence?
   - What's the one thing the essay MUST get right to maintain credibility?

4. **The "So What?" Test**: After reading this essay, what does the reader DO differently? Think differently? See differently? If the answer is nothing, the essay has failed.

5. **The AI Detection Radar**: Read this topic through the lens of a 2026 reader who has seen hundreds of AI-generated takes on similar subjects. What will make them suspect AI?
   - Which phrasings or structures are AI-typical for this specific topic?
   - What "both sides" framings would an LLM default to?
   - What evidence or specifics would only a human include?
   - What personal risk or genuine uncertainty signals human authorship?

## Output

- **Skepticism Map** (3-5 key objection points with responses)
- **Boredom Points** (ranked, with fixes)
- **Trust Requirements** (what must be established)
- **The Transformation** (what changes in the reader)
- **AI Detection Risks** (topic-specific tells to avoid)
"""
)
```

### Agent 5: The Anti-Slop Enforcer

```
Task(
  subagent_type="general-purpose",
  description="Anti-Slop Enforcement: 2026-calibrated essay watchlist",
  model="opus",
  prompt="""You are the anti-slop enforcer. Your job: create a pattern watchlist calibrated to 2026 reader sensitivity. This is not the audiobook watchlist. This is essay-specific.

In 2026, readers have spent two years swimming in AI-generated content. They've developed pattern-recognition that operates below conscious awareness. A UCC study using literary stylometry confirmed: AI writing has a detectable stylistic fingerprint even when individual sentences pass detection. The fingerprint is structural, not lexical.

TOPIC: [PASTE TOPIC AND SOURCE SUMMARIES]
ESSAY TYPE: [DETECTED TYPE]

## The 2026 Reader's Antibodies

These are what readers now unconsciously flag:

**Structural tells** (the essay SHAPE screams AI):
- Balanced treatment of every perspective (AI is constitutionally fair)
- Every paragraph landing with similar energy
- Perfect topic-sentence-to-elaboration ratio throughout
- Transitions that explicitly announce what's coming
- Conclusions that recapitulate earlier points
- Every section the same approximate length
- No loose ends, no unresolved tensions

**Lexical tells** (the WORDS scream AI):
- "Landscape" / "tapestry" / "fabric" / "mosaic" used as metaphors
- "Navigating" anything abstract
- "Nuanced" / "multifaceted" / "intricate"
- "It's worth noting" / "importantly" / "significantly"
- "Raises important questions"
- "At the heart of"
- "Not just X, but Y"
- "In an era of..."
- "Delve into" / "unpack" / "explore"
- Paired adjectives where one would do ("comprehensive and thorough")

**Rhetorical tells** (the MOVES scream AI):
- Opening with a sweeping contextual statement
- "Imagine..." as a paragraph opener
- Posing a rhetorical question and answering it in the next sentence
- The "to be sure" concession (acknowledging a counterpoint only to dismiss it)
- Ending on an aspirational note about the future
- Using "we" to create false solidarity with the reader
- "The truth is..." or "The reality is..." as revelation markers

**Tonal tells** (the FEEL screams AI):
- Uniform confidence throughout (humans waver)
- No genuine self-correction mid-argument
- Emotional claims without emotional texture (saying something is "devastating" in flat prose)
- Optimistic endings on dark subjects
- Equal facility with every subtopic (humans have uneven expertise and it shows)

## Your Mission

Create a comprehensive enforcement watchlist for THIS specific essay:

1. **40-Item Pattern Watchlist**: Organized by category. Include the audiobook's 35 patterns, PLUS essay-specific additions. For each: the pattern, why it fails, what to do instead.

2. **Topic-Specific Traps**: What cliches, framings, and phrasings are AI-typical for THIS specific topic?

3. **Structural Enforcement Rules**:
   - Maximum and minimum section lengths (force variance)
   - Required structural asymmetries
   - Mandated moments of uncertainty or self-correction
   - Banned transition patterns

4. **The Sentence-Level Audit**:
   - Sentence-length standard deviation target (minimum 5 words)
   - Maximum consecutive sentences of similar length: 2
   - Minimum register shifts per 1,000 words: 3
   - Maximum evaluative adjectives per 1,000 words: 4
   - Required ratio of concrete to abstract sentences: at least 1:2

5. **Scoring Rubric**: 6 dimensions, 10 points each, target 48+/60

## Output

- **40-Item Watchlist** (with alternatives)
- **Topic-Specific Traps** (this essay's unique risks)
- **Structural Enforcement Rules**
- **Sentence-Level Audit Specs**
- **Scoring Rubric** (6 dimensions defined with scoring criteria)
"""
)
```

---

## Phase 3: Synthesis + Structural Decision

After all 5 agents return, synthesize their outputs.

### 3.1 Resolve Tradeoffs

For each tension between agents, document:
```
TRADEOFF: [topic]
- Agent X says: [position] because [reasoning]
- Agent Y says: [position] because [reasoning]
- Resolution: [chosen approach with rationale]
```

Common tradeoffs:
- **Angle vs. Audience**: The Contrarian wants a sharp take; the Reader's Advocate worries it'll alienate. Resolution: sharpen the take but earn it with evidence.
- **Structure vs. Voice**: The Architect wants formal structure; the Essayist wants organic flow. Resolution: structure is invisible scaffolding, not visible architecture.
- **Surprise vs. Credibility**: A surprising claim must be backed. If it can't be backed, it becomes a question rather than a claim.
- **Economy vs. Texture**: Op-eds demand economy; long-form needs breathing room. The essay type resolves this.

### 3.2 Lock the Core Claim and the Surprise

Write in one sentence: **The essay argues that [CLAIM] because [REASONING], which surprises because [WHAT READERS EXPECT INSTEAD].**

If you can't write this sentence, the essay is not ready to write. Return to Phase 2.

### 3.3 Define Section Architecture

Create a table:
| Section | Working Title | Word Budget | The Move | The Turn | Voice Notes |
|---------|---------------|-------------|----------|----------|-------------|
| Opening | "..." | 150-300 | [What it does] | [Where it shifts] | [Texture] |
| 1 | "..." | [budget] | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |
| Landing | "..." | 150-300 | [What it does] | [Final shift] | [Texture] |

### 3.4 Establish Production Rules

Document final rules for:
- **Structure**: Chosen mode, section constraints, required asymmetries
- **Voice**: Active commitments from Agent 3's profile
- **Anti-slop**: Top 20 patterns to watch during writing (from Agent 5's 40)
- **Reader trust**: Key moments where credibility must be established

---

## Phase 4: Writing

### 4.1 The Opening (First 200 Words)

The opening must EARN the reader's next 200 words. It must do one of:
- **Make a claim that provokes**: State something the reader will want to argue with
- **Present a scene that disorients**: Drop the reader into a concrete moment that raises a question
- **Confess something that costs**: Admit uncertainty, failure, or confusion that earns trust
- **State a fact that defamiliarizes**: Take something familiar and make it strange

The opening must NOT:
- Begin with a sweeping contextual statement ("In today's world...")
- Begin with a dictionary definition
- Begin with a rhetorical question
- Begin with "Imagine..."
- Begin with a famous quote
- Begin by announcing what the essay will do

### 4.2 Write Body Sections

For each section:
1. Execute the MOVE defined in the architecture
2. Include the TURN where the reader's understanding shifts
3. Deploy the assigned essay moves from Agent 3
4. Honor the texture map (dense/breathing/fast/slow)
5. Vary sentence length aggressively (SD > 5 words)
6. Shift register at least once per section
7. Ground every abstraction in a concrete particular
8. If a section feels complete and tidy, break something open

### 4.3 The Landing

The ending is NOT:
- A summary of what was argued
- A call to action
- A prediction about the future
- An inspirational closing thought
- A return to the opening image (unless it has genuinely transformed)

The ending IS:
- A shift in altitude: pull back to reveal what the accumulated argument has built
- OR: a quiet sentence that lands without fanfare
- OR: a new question that the essay has earned the right to ask
- OR: an image that contains the argument without stating it
- OR: a confession about what the essay failed to resolve

### 4.4 Anti-Slop Pass

After writing, execute a rigorous scan:

**Pass 1 -- Lexical**: Search for every item on the 40-pattern watchlist. Replace or delete each instance.

**Pass 2 -- Structural**: Check section lengths for variance. Check that not every section ends with similar energy. Check that transitions don't all announce what's coming. Check that the essay contains at least one genuine self-correction.

**Pass 3 -- Tonal**: Read for uniform confidence. Introduce genuine uncertainty where the topic warrants it. Check that emotional claims have emotional texture in the prose around them.

**Pass 4 -- The First Sentence Test**: Read only the first sentence of every paragraph in sequence. Do they form a coherent argument on their own? They should not -- that's a sign of formulaic topic-sentence structure. They should create an unpredictable rhythm that pulls the reader forward.

**Pass 5 -- The Deletion Test**: For every paragraph, try deleting the first sentence. If the paragraph survives without it, the first sentence was throat-clearing. Cut it.

---

## Phase 5: Quality Assurance

### 5.1 Self-Score (Target: 48+/60)

| Dimension | Definition | Scoring | Score |
|-----------|------------|---------|-------|
| **Surprise** (1-10) | Does the essay tell the reader something they didn't know? Count the genuine surprises: facts, connections, reframings. 0 surprises = 1 point. 1 = 4. 2 = 6. 3+ = 8-10 depending on quality. | |
| **Precision** (1-10) | Are claims as strong as possible without being false? Count hedging phrases ("it could be argued", "one might say", "perhaps"). Each purposeless hedge costs 1 point. Count vague claims that could be made more specific. Each costs 0.5. Start at 10, subtract. | |
| **Texture** (1-10) | Does the prose move between abstraction levels? Check: concrete-to-abstract sentence ratio (target 1:2 or better). Check sentence-length standard deviation (target > 5). Check register shifts (target > 3 per 1,000 words). Each target missed costs 2 points. | |
| **Voice** (1-10) | Would a reader recognize this writer from another piece? Check: does the essay contain at least 2 moments of genuine self-correction or admission of uncertainty? Does it contain at least 1 moment where the writer risks something (an unpopular claim, a personal admission, a confession of ignorance)? Missing either costs 3 points. | |
| **Stakes** (1-10) | Does the reader care? Check: can you state what changes if this essay is right? Can you state what goes wrong if it's ignored? Can you identify who specifically is affected? Each missing element costs 2 points. Does the essay answer the "so what?" test from Agent 4? If not: 4 max. | |
| **Architecture** (1-10) | Does the structure serve the argument? Check: does every section make a distinct MOVE? Is there at least one turn that reframes everything before it? Does the ending shift altitude rather than summarize? Does the essay contain structural asymmetry (sections of different lengths, different energies)? Each failure costs 2 points. | |

**If score < 48**: Identify the weakest dimension. Rewrite the sections that most affect that dimension. Re-score.

**If score >= 48 but < 54**: The essay is publishable. Note which dimensions could improve and offer the user targeted revision suggestions.

**If score >= 54**: The essay is exceptional. Output without further revision.

### 5.2 Output

Write the final essay to a single MD file:
- Clean prose, publication-ready
- Section breaks as `---` or blank lines (not numbered headers unless the essay form calls for them)
- No meta-commentary about the writing process
- No "in this essay" or "as we've seen" or "to conclude"
- The title should be evocative, not descriptive (unless the essay type demands clarity, as in technical essays)

---

## Voice Guide: The Seven Commitments

Unlike the audiobook's Michael Caine persona, the essay skill does not impose a character. It imposes commitments that produce voice AS A CONSEQUENCE of honest thinking.

### Commitment 1: Think Visibly
Show the machinery of thought. Not performatively ("Let me think about this...") but structurally: the essay's movement should trace the movement of a mind encountering its subject. Include moments where the argument turns, reconsiders, or complicates itself.

### Commitment 2: Concrete First
Never begin a section, paragraph, or argument with an abstraction. Begin with a particular: a scene, a number, a name, an image, a sensation. Abstractions are conclusions, not starting points.

### Commitment 3: Earn Every Claim
For every evaluative adjective (important, significant, devastating, remarkable), check: has the essay SHOWN this quality, or is it ASSERTING it? If asserting, either show it or cut the adjective.

### Commitment 4: Risk Something
The essay must contain at least one moment where the writer is vulnerable: an unpopular claim, a personal admission, an honest "I don't know." Without risk, there are no stakes. Without stakes, there is no reader.

### Commitment 5: Vary Everything
Sentence length. Paragraph length. Section length. Register. Energy level. Confidence level. The only pattern is the absence of pattern. AI writing is detectable precisely because it maintains consistency. Human writing drifts, spikes, dips, recovers.

### Commitment 6: Trust the Reader
Never explain a metaphor after deploying it. Never tell the reader what to conclude. Never recap what you've already said. The reader is at least as smart as the writer. Treat them that way.

### Commitment 7: End Unresolved
Not every tension needs resolving. Not every question needs answering. The best essays leave the reader with productive discomfort -- a question they'll keep thinking about after they close the tab. Tidy endings signal that the essay was never really exploring; it was just performing exploration.

---

## Stop-Slop Reference: The 2026 Essay Watchlist

### Category A: Opening Kills (Never Start With These)
1. "In today's [anything]" / "In an era of" / "In a world where"
2. "Imagine..." as the first word
3. Dictionary definitions ("Webster's defines...")
4. Famous quotes as epigraphs (unless genuinely earned later)
5. Rhetorical questions that the essay immediately answers
6. "I've always believed..." (AI's fake personal history)
7. "When I first heard about X, I thought Y. I was wrong."
8. Sweeping historical claim ("Since the dawn of civilization...")

### Category B: Filler Phrases (Cut These)
9. "It's worth noting that" / "It's important to recognize"
10. "The reality is" / "The truth is" / "Here's the thing"
11. "Let that sink in" / "Think about that for a moment"
12. "At the end of the day"
13. "Needless to say" (then don't say it)
14. "In other words" (say it right the first time)
15. "Simply put" / "Put simply" / "To put it bluntly"
16. "Interestingly enough" / "Fascinatingly" / "Remarkably"
17. "The fact of the matter is"
18. "It goes without saying" (it does, so don't)
19. "To be fair" (as a dismissive concession)
20. "Make no mistake"

### Category C: Profundity Markers (Rewrite These)
21. "Profound implications" / "seismic shift" / "watershed moment"
22. "Game-changer" / "paradigm shift" / "transformative"
23. "Raises important questions" (which questions? ask them)
24. "And that changes everything" (show the change; don't announce it)
25. "At its core" / "fundamentally" / "ultimately"
26. "Ever-evolving landscape" / "rapidly changing world"
27. "Not just X -- but Y" (the AI reveal structure)
28. "Speaks to a larger truth about"

### Category D: Structural Tells (Vary These)
29. "Not X. Y." binary contrast reveals -- max 1 per essay
30. Every paragraph opening with a topic sentence
31. Three-item lists (two items beat three; four beats three)
32. Orphan dramatic fragments ("Gone." "Nothing." "Zero.") -- max 1 per essay
33. Em-dash before a reveal -- max 2 per essay
34. Balanced "on one hand / on the other" constructions
35. Transition words that announce structure ("First... Second... Finally...")
36. Concluding paragraphs that begin with "In conclusion" / "Ultimately" / "At the end of the day"
37. Sections of identical length (force +/- 20% variance)
38. Every section ending at the same energy level

### Category E: Voice Kills (Eliminate These)
39. Wisdom-dispenser constructions ("X isn't about Y. It's about Z.")
40. Anthropomorphism treadmill: ideas "wrestle," "grapple," "dance with"
41. Rhetorical questions answered in the next sentence
42. "We" used to create false solidarity (unless the essay genuinely speaks for a group)
43. "Perhaps" / "Maybe" hedging without genuine uncertainty
44. Paired synonyms where one would do ("comprehensive and thorough", "clear and evident")
45. "Of course" as dismissive cushion
46. "In fact" / "Actually" as intensifiers rather than corrections
47. Explaining metaphors after deploying them
48. Consecutive sentences of matching length (break one)
49. "It could be argued that" (argue it, or don't)
50. Optimistic pivot at the end of a dark essay ("But there is hope...")

---

## Essay Type Adaptations

### Long-Form (4,000-7,000 words)
- Requires at least 2 structural turns (moments where everything reframes)
- Deploy the braided or spiral structure
- Include at least one extended scene or narrative passage (300+ words of concrete storytelling)
- Allow digressions -- but each digression must earn its way back to the main argument
- The reader should feel that cutting any section would damage the whole

### Op-Ed (800-1,200 words)
- One claim. One structure. Total economy.
- Every sentence must either advance the argument or provide evidence
- No digressions, no texture passages, no extended scenes
- The opening sentence should contain the claim or its seed
- Maximum 5 paragraphs
- The ending should land like a closing argument, not trail off

### Technical Essay (2,000-4,000 words)
- Use the ladder of abstraction: concrete example -> principle -> concrete example -> deeper principle
- Every technical concept must be grounded in an analogy or example before being named
- The reader should understand the concept before they learn the terminology
- Include at least one moment where the essay acknowledges the limits of its explanation
- Avoid false simplification: say "this is more complex than I'm making it sound, but the core insight holds"

### Personal Essay (1,500-3,500 words)
- The braided or hermit crab structure works best
- The personal experience must connect to something larger without the essay announcing the connection
- Emotional honesty without sentimentality: show, don't tell feelings
- Include at least one moment of genuine vulnerability
- The reader should learn something about themselves by reading about the writer
- Avoid the "and then I realized..." epiphany structure. Epiphanies are earned, not announced.

### Persuasive Essay (1,500-3,000 words)
- Use the dialectical structure: present the strongest version of the opposing view before engaging with it
- Never straw-man the opposition
- Earn agreement through evidence and reasoning, not assertion
- Include at least one genuine concession to the other side that you don't immediately take back
- The reader should feel that the essay has considered their objections before they raise them

### Exploratory Essay (2,000-5,000 words)
- Use the spiral structure: the essay discovers its conclusion; the reader watches
- Begin with a genuine question, not a thesis
- Allow the essay to surprise itself -- include at least one moment where the argument goes somewhere the writer didn't expect
- The ending should feel discovered, not predetermined
- This is the essay type most likely to benefit from the "thinking on the page" commitment

---

## Example Output Structure

```markdown
# The Title: Evocative, Not Descriptive

The opening move. A scene, a claim, a confession, a fact that makes
something familiar strange. No throat-clearing. The essay begins mid-thought
because essays are not speeches.

The first section develops the initial move. It introduces the core tension.
It grounds abstractions in specifics. A number, a name, a place. The prose
breathes -- some sentences long and winding, others short. Like this.

---

A section break signals a shift. Not a new chapter -- a new angle on the same
subject. The braided essay introduces its second thread here. The spiral essay
returns to its core idea from a new altitude. The dialectical essay presents
its complication.

Something concrete: a scene, an anecdote, a piece of evidence that does not
merely illustrate but ADVANCES the argument. The essay's temperature changes.
Pace shifts. The writer admits something -- uncertainty, surprise, the limits
of their knowledge.

---

The turn. Everything before this looked one way. Now it looks different. Not
because the essay contradicted itself, but because it accumulated enough
material for a new pattern to emerge. This is where the reader's understanding
shifts.

The prose may slow here. A difficult idea needs room. Or it may accelerate --
the implications cascade and the writer chases them.

---

The landing. Not a summary. A shift in altitude. The reader sees the subject
from a new vantage -- one the essay built without announcing it was building
anything. The final sentences are quiet. Or they aren't. They're whatever the
essay needs them to be.

Some essays end with a question. Some with an image. Some with a sentence so
plain it becomes a kind of silence.
```

---

## Triggers

- `/essay`
- "write an essay"
- "essay about"
- "write a long-form piece"
- "write an op-ed"
- "write a think piece"
- "personal essay about"
- "technical essay on"
