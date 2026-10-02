# PLAN_NOW (2026-10-02)

The plan has changed. PLAN_NOW.md overrides IMPLEMENTATION.md and SPEC.md where they differ.

Why: v1 reads Naskh well (90%) but not Thuluth/Diwani (20–25%), and when it fails it writes a famous verse
that is not on the panel. So we no longer identify ornate panels by reading them.

Product flow:
1. Photo → match against our panel collection (photos the team took, each verse confirmed by the team).
2. No match and the text is Naskh → v1 reads it → search the Quran → show the verse only if score ≥ 90
   and every line points to the same place in the Quran.
3. Otherwise → "Couldn't identify this panel reliably" + ask a guide. Never guess.
4. Verse card: Quran text copied from QuranEnc (never generated), reference, approved English translation,
   human recitation audio.
5. Chat: answers only from approved sources with citations; follows the 4 content levels;
   personal fatwa questions → general info + referral.

Cut: synthetic data, training KhaṭṭVision v2 (M7–M9), Sharia reviewer sign-off, the 8–15 person user test,
HF release of synthetic data. Instead: automated tests + a 1-hour team check on Oct 6
(12 official questions, 10 random verse cards, 3 trick questions).
Open source: the code + a small dataset of the team's own panel photos. Never DuwatBench or
freeislamiccalligraphy images.

Schedule:
- Oct 2–3 [PRE]: photo-matching test, corpus (M1), skeleton (M4), PRIOR_WORK.md + tag pre-challenge before Oct 4 09:00.
- Oct 4: whole flow live on HTTPS (photo → match → card → chat).
- Oct 5: Naskh path, chat with sources + 4 levels, 12 official questions pass.
- Oct 6: polish, team check, demo video + deck, submit by 22:00.
