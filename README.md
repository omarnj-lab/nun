# Nūn · handoff to the GPU server

Everything Claude Code needs to implement Nūn on your GPU server, and the human tasks that unblock it.

| File | What it is | Who reads it |
|---|---|---|
| `CLAUDE.md` | Project memory: what Nūn is, non-negotiable rules, architecture, repo layout, commands | Claude Code, automatically, every session |
| `SPEC.md` | Technical specification: corpus, normalisation, scan pipeline, prompts, training, API contract, agent, guards, eval, UI, deployment | Claude Code |
| `IMPLEMENTATION.md` | Milestones M0–M15 with owners, `[PRE]`/`[BUILD]` tags, "done when" checks, the 3-day schedule, human task list | Claude Code + team |
| `RULES.md` | Challenge rules, the scientific package (4 content levels, approved references, 12 official test questions, glossary), judging rubrics, `PRIOR_WORK.md` template | Claude Code + team |
| `SOURCES.md` | Every data source with endpoint, terms, attribution and status (becomes `docs/SOURCES.md`) | Claude Code + reviewer |
| `.env.example` | Keys and settings the server needs | Team |
| `brand/` | Logo (SVG/PNG), app icon | Web app |
| `context/` | Idea deck, brand sheet, strategy plan, registration text, participant guide, scientific package, official presentation template, teaser video | Reference |

## Moving it to the server
```bash
# from this Mac
cd ~/Desktop/Hackathones/IslamicHackthone
zip -r Nun_handoff.zip handoff
scp Nun_handoff.zip <user>@<server>:~/

# on the server
unzip Nun_handoff.zip && mv handoff nun && cd nun
git init && git add -A && git commit -m "Nūn handoff: spec, plan, rules, sources, brand"
cp .env.example .env    # fill in the keys
claude                  # start Claude Code in this folder (it loads CLAUDE.md)
```

## First prompts for Claude Code
1. `Read CLAUDE.md, SPEC.md, IMPLEMENTATION.md, RULES.md and SOURCES.md. Then do milestone M0 only. Report the GPU tier you chose, v1 smoke-test results, and anything that blocks you. Log it in PROGRESS.md.`
2. `Do M1 (corpus). Stop and show me the reviewer drafts (names, dhikr, inscriptions list) before finalising them.`
3. `Do M3's tooling (Commons collector + labelling tool) and M4 (scaffolding). Then write PRIOR_WORK.md and create the pre-challenge tag.` (must finish before Oct 4 09:00 Riyadh)
4. On Oct 4 at 09:00: `Start Phase 1. Follow the Day 1 schedule in IMPLEMENTATION.md. The walking skeleton (M5 + M6) comes first.`

Work one milestone at a time, and check its "done when" list before moving on.

## Important
- **Only work done Oct 4–6 is scored.** Before that, do only the `[PRE]` milestones and declare them (`PRIOR_WORK.md` + tag).
- The **scientific package** (`RULES.md` §3) is what the judges score reliability against. The four content levels and the 12 test questions are built into the agent spec and its test suite.
- Open decisions are marked 🔴 in `SOURCES.md`: the fr/ur/id/zh translation choices, which tafsir to use, and the recitation/Bayyinat/Jamhara terms. Resolve them before Oct 4.
