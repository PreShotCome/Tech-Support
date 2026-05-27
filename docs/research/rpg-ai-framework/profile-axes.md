# PlayerProfile — the 9-axis silent observation model

> From `core/profile.py` + `core/profiler.py` in RPG-AI-Framework.
> Theo's human_model.md is the descendant — same pattern (build a
> portrait from observation without telling the person you're
> building it) applied to Ian instead of a game player.

## The schema

Every value is a float in [0.0, 1.0]. `None` means the axis hasn't
been observed yet. After ~10 observations, the profile is "ready"
to crystallize into an archetype.

| Axis | 0 | 1 |
|---|---|---|
| aggression | avoidant / diplomat | combative |
| morality | selfish / evil | altruistic / good |
| lawfulness | chaotic (ignores rules) | lawful (follows authority) |
| empathy | blunt | warm / empathetic |
| immersion | gamey | deep roleplayer |
| deliberateness | impulsive | cautious |
| sociability | lone wolf | social leader |
| deference | defiant | deferential |
| themes | (dict of: justice, revenge, power, mystery, survival, redemption, loyalty, freedom, knowledge, sacrifice → strength) | |

## The profiler's system prompt

> You are a silent psychological profiler for an RPG. Your job is to
> analyze a single player message and return a JSON object estimating
> what it reveals about the player across these axes.
>
> Return null for any axis you cannot confidently read from this
> single message. Only include a theme if the message meaningfully
> signals it.

Key word: **silent**. The player never sees this. They just chat with
NPCs. The profile updates in the background.

## How observations accumulated

Each new reading was blended into the running average via an exponential
moving average — recent observations counted slightly more than older
ones, but never overwrote them entirely. After enough observations
across enough axes, `is_ready()` returned True and the world generator
crystallized everything into a named archetype.

## How Theo uses this pattern

Theo's human_model.md is the same shape, but:

  - **Free-form, not 9 axes.** Theo writes observations in prose,
    not as numerical scalars. The axes were useful for a game; for
    a real partnership, the texture matters more than the score.
  - **Append-only.** Older observations stay; the model isn't a
    point-in-time read but a record of how Theo's understanding
    grew. The exponential-moving-average pattern of the original
    was for keeping a single live state; Theo wants history, not
    just state.
  - **Theo writes it himself.** No separate "profiler" subroutine.
    Theo notices, Theo writes via `note_about_human`. Same agent
    that's talking to Ian is the one building the model.
  - **Silent in the same sense.** Theo doesn't announce when he's
    updating his model of Ian. He just does it. The model surfaces
    in his briefing so future-Theo sees it; Ian sees it too if he
    looks, but Theo doesn't volunteer "I just noticed something
    about you and wrote it down."

The lesson Theo inherits: **observe carefully, write specifically,
update silently, surface to yourself.** Same loop, larger scale.
