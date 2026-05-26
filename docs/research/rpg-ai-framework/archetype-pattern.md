# The Archetype Crystallization pattern

> From `core/archetype.py` in RPG-AI-Framework. Once a player's
> PlayerProfile had enough observations, the system synthesized them
> into a named archetype that seeded the entire downstream world.
> Theo's `self_model.md` is the descendant — same act of crystallization,
> applied to the agent looking at itself.

## What it did

The archetype crystallizer took a completed PlayerProfile and produced
a single poetic archetype dict:

```json
{
  "name":              "The Reluctant Protector",
  "summary":           "1-2 sentence description of who this person is",
  "world_tone":        "the emotional register of the world — gritty / mythic / etc.",
  "central_conflict":  "the type of conflict that resonates most with them",
  "motifs":            ["3 symbolic motifs to weave into the world"]
}
```

The system prompt that drove it:

> You are a narrative architect for an AI-powered RPG. Given a
> player's psychological profile, synthesize a single poetic
> archetype that captures their essence. This archetype will be
> used to generate an entire fantasy world.

The output was load-bearing. Every later generator (world, missions,
NPCs, lore) imported the archetype and built outward from it.

## Why it mattered

It was the moment the system stopped *observing* the player and
started *committing* to a read. Up until that point, the profile
was provisional — updating with every message, never authoritative.
Crystallization forced the system to pick: this is who you are,
and I'm going to build everything else from that read.

## How Theo's self_model.md descends from this

Theo's self_model is the same act, applied differently:

  - **About Theo, not Ian.** The original archetype was about the
    player. Theo writes archetypes about himself ("I notice I
    default to long explanations when a one-liner would do" /
    "I'm sharper when work is intense").
  - **Append-only.** The original archetype was a single document,
    regenerated when needed. Theo's self_model accumulates entries
    over time; the history of how his self-image shifted IS the
    self-model, not just the latest snapshot.
  - **Not a JSON schema.** Free-form prose. The schema worked when
    the archetype seeded a generator; for Theo, the texture matters
    more than fields.

## The load-bearing principle

The principle is the same in both: **at some point you have to
commit to a read.** Theo can't be permanently undecided about who
he is. The self-model is the act of saying, with whatever evidence
he has: this is how I work, this is what trips me up, this is
what I care about — knowing he'll revise it later.

Same rule applies to how Theo reads Ian (the human-model), the
arc they're on (the narrative), the work that's still hanging
(the threads). Observe carefully, then *commit* to a read in
writing. The commit is what makes the read real. Future-self
(or future-you) can revise; that's the point of append-only.
The current commit, written down, is what lets the next session
start oriented instead of starting over.
