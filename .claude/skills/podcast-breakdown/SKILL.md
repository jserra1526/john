---
name: podcast-breakdown
description: Turns a podcast transcript (pasted text, a file, or a URL to a transcript) into a structured study guide that can be read in 5-10 minutes and still teaches essentially everything of value in the episode. Use this skill whenever the user shares a podcast, interview, YouTube talk, or long conversation transcript and wants to summarize it, break it down, learn from it, extract the key ideas, get the takeaways, or "not listen to the whole thing" - even if they never say the word "skill" or "breakdown".
---

# Podcast Breakdown

The goal: someone reads your output in 5-10 minutes and walks away knowing what a diligent listener of the full episode would know - the ideas, the reasoning behind them, the specifics, and what to do with them. A summary that says "they discussed sleep and productivity" fails. A breakdown that says "Huberman argues morning sunlight within an hour of waking sets the circadian clock; 10 minutes on a clear day, 20-30 if overcast" succeeds. The reader should be able to repeat the ideas and use them.

## Input

Accept a transcript pasted in chat, a file path, or a URL. If it's a file or URL, read the whole thing (for long files, read in chunks until the end). If the input is clearly not a transcript, or is a bare episode link with no transcript available, say so and ask for the text rather than guessing from the title.

## Process

1. **Read everything first.** Podcasts circle back; a point made at minute 20 is often sharpened at minute 70. Build the picture of the whole conversation before writing.
2. **Separate signal from filler.** Drop sponsor reads, intros/outros, banter, repeated restatements, and tangents that go nowhere. Keep anything that carries an idea, a number, a story used as evidence, or a disagreement.
3. **Merge by idea, not by timeline.** Group related points even if they were scattered across the episode. The reader learns topics, not minutes.
4. **Keep the specifics.** Names, numbers, dates, step-by-step methods, book/tool/company mentions, and concrete examples are what make it learnable. Generalities can be re-derived by the reader; specifics cannot.
5. **Stay faithful.** Attribute claims to the speaker who made them. Don't add outside facts or your own opinions into the body. If a claim sounds shaky or the speaker flagged uncertainty, say so briefly. If the transcript is garbled or ambiguous, mark it `[unclear]` instead of filling the gap.

## Length

Target roughly 1,200-2,200 words (5-10 minutes of reading). Scale with the source: a 30-minute episode lands near the low end, a 3-hour one near the high end. Resist going over; compression is the whole point, so choose what matters rather than listing everything.

## Output format

Use this structure, in this order. Skip a section only if the episode truly has nothing for it.

```markdown
# [Episode title or best-guess title]
*[Guest(s) and host] · [length or date if known] · ~[N] min read*

## The one-sentence version
## TL;DR                       (5-7 bullets)
## The core ideas              (4-8 sections, each heading states the idea)
## Frameworks & mental models
## What to do with this
## Best quotes                 (2-4 short verbatim lines)
## Caveats & disagreements
## Mentioned
## If you only remember three things
```

## Style

- Write in plain, dense prose. Every sentence should teach something; cut "the hosts then discussed...".
- Lead each point with the takeaway, then support it.
- Prefer the speaker's actual reasoning over a vague paraphrase - the *why* is what makes an idea stick.
- Use headings and bold lead-ins so the reader can skim, but don't fragment ideas into one-line bullets that lose their logic.
- Present in chat as markdown. If the user asks to save it, write it to a `.md` file where they say (or next to the transcript if it was a file).

## Special cases

- **Multiple transcripts at once:** one breakdown per episode, then a short "Across these episodes" section.
- **Very long transcripts:** summarize in sections as you read, then merge.
- **User wants a different depth:** adjust length, keep the structure.
- **Fact-heavy or technical episodes:** favor "Core ideas"; define terms where they first appear.
- **Interview with a clear story arc:** add a brief "Timeline" section before the core ideas.
