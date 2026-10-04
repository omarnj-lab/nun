"""Download the Quran sources and build data/corpus/quran.jsonl + MANIFEST.json (SPEC §3.1).

Usage: python -m nun.corpus.build [--data data] [--offline]
Raw responses are cached byte-for-byte under data/raw/ and re-used unless deleted.
Any failed build check raises and nothing is written to data/corpus/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from nun.corpus.models import QuranRecord, TranslationText
from nun.corpus.sources import (
    AUDIO_ALAFASY,
    EXPECTED_AYAHS,
    EXPECTED_SURAS,
    QURANENC_API,
    TAFSIR,
    TANZIL_DOWNLOAD,
    TANZIL_METADATA,
    TRANSLATIONS,
    USER_AGENT,
)
from nun.normalize.arabic import normalize, normalize_ns


class BuildError(RuntimeError):
    pass


def fetch(url: str, dest: Path, offline: bool, retries: int = 4) -> bytes:
    if dest.exists():
        return dest.read_bytes()
    if offline:
        raise BuildError(f"missing cached file in --offline mode: {dest}")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            return body
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_tanzil(raw: bytes) -> dict[tuple[int, int], str]:
    out = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        s, a, text = line.split("|", 2)
        out[(int(s), int(a))] = text
    return out


def parse_metadata(raw: bytes) -> tuple[dict[int, dict], list[tuple[int, int, int]]]:
    root = ET.fromstring(raw)
    suras = {int(e.get("index")): dict(e.attrib) for e in root.iter("sura")}
    juz = [(int(e.get("index")), int(e.get("sura")), int(e.get("aya"))) for e in root.iter("juz")]
    return suras, sorted(juz)


def juz_of(sura: int, aya: int, juz_starts: list[tuple[int, int, int]]) -> int:
    current = 1
    for idx, s, a in juz_starts:
        if (sura, aya) >= (s, a):
            current = idx
    return current


def build(data: Path, offline: bool = False) -> dict:
    raw_dir = data / "raw"
    started = datetime.now(UTC).isoformat(timespec="seconds")
    manifest: dict = {"built_at": started, "sources": {}, "checks": {}, "outputs": {}}

    # --- Tanzil
    tanzil = {}
    for t in ("simple-clean", "uthmani"):
        url = TANZIL_DOWNLOAD.format(type=t)
        body = fetch(url, raw_dir / "tanzil" / f"quran-{t}.txt", offline)
        tanzil[t] = parse_tanzil(body)
        manifest["sources"][f"tanzil:{t}"] = {"url": url, "sha256": sha256(body), "version": "Tanzil v1.1"}
    meta_raw = fetch(TANZIL_METADATA, raw_dir / "tanzil" / "quran-data.xml", offline)
    suras, juz_starts = parse_metadata(meta_raw)
    manifest["sources"]["tanzil:metadata"] = {"url": TANZIL_METADATA, "sha256": sha256(meta_raw)}

    # --- QuranEnc (translations + tafsir), per sura
    versions_raw = fetch(f"{QURANENC_API}/translations/list", raw_dir / "quranenc" / "translations_list.json", offline)
    listed = {t["key"]: t for t in json.loads(versions_raw)["translations"]}
    keys = list(TRANSLATIONS) + list(TAFSIR)
    jobs = [(k, s) for k in keys for s in range(1, EXPECTED_SURAS + 1)]

    def get(job: tuple[str, int]) -> tuple[str, int, bytes]:
        k, s = job
        url = f"{QURANENC_API}/translation/sura/{k}/{s}"
        return k, s, fetch(url, raw_dir / "quranenc" / k / f"{s:03d}.json", offline)

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(get, jobs))

    qe: dict[str, dict[tuple[int, int], dict]] = {k: {} for k in keys}
    digests: dict[str, hashlib._Hash] = {k: hashlib.sha256() for k in keys}
    for k, _s, body in sorted(responses, key=lambda r: (r[0], r[1])):
        digests[k].update(body)
        for row in json.loads(body)["result"]:
            qe[k][(int(row["sura"]), int(row["aya"]))] = row
    for k in keys:
        info = listed.get(k, {})
        manifest["sources"][f"quranenc:{k}"] = {
            "url": f"{QURANENC_API}/translation/sura/{k}/{{sura}}",
            "version": info.get("version"),  # None = not in QuranEnc's published list (e.g. arabic_moyassar)
            "last_update": info.get("last_update"),
            "title": info.get("title"),
            "status": (TRANSLATIONS.get(k) or TAFSIR[k])["status"],
            "sha256_all_suras": digests[k].hexdigest(),
        }

    # --- checks
    failures: list[str] = []
    checks = manifest["checks"]
    refs = sorted(tanzil["simple-clean"])
    checks["ayah_count"] = len(refs)
    if len(refs) != EXPECTED_AYAHS:
        failures.append(f"Tanzil simple-clean has {len(refs)} ayahs, expected {EXPECTED_AYAHS}")
    checks["sura_count"] = len({s for s, _ in refs})
    if checks["sura_count"] != EXPECTED_SURAS or len(suras) != EXPECTED_SURAS:
        failures.append("sura count mismatch")
    for s, m in suras.items():
        n = sum(1 for (ss, _) in refs if ss == s)
        if n != int(m["ayas"]):
            failures.append(f"sura {s}: {n} ayahs vs metadata {m['ayas']}")
    for name, table in [("tanzil:uthmani", tanzil["uthmani"])] + [(f"quranenc:{k}", qe[k]) for k in keys]:
        if sorted(table) != refs:
            failures.append(f"{name}: ayah refs differ from Tanzil simple-clean ({len(table)} rows)")

    # Uthmani text identical in every QuranEnc key (one source of truth for display)
    primary = "english_saheeh"
    uthmani_diff = [
        f"{s}:{a}"
        for (s, a) in refs
        for k in keys
        if qe[k][(s, a)]["arabic_text"] != qe[primary][(s, a)]["arabic_text"]
    ]
    checks["uthmani_identical_across_quranenc_keys"] = not uthmani_diff
    if uthmani_diff:
        failures.append(f"arabic_text differs between QuranEnc keys at {uthmani_diff[:10]}")

    # Tanzil (simple-clean and uthmani) writes the sura-header Basmala at the start of aya 1 of every sura except
    # 1 and 9. It is not part of that ayah (QuranEnc omits it), so it is separated from text_simple here; the verse
    # text itself is unchanged. 1:1 and 27:30 keep their Basmala (it is the verse).
    basmala_simple = tanzil["simple-clean"][(1, 1)]
    basmala_uthmani = tanzil["uthmani"][(1, 1)]
    headers_removed = []

    records = []
    empty = []
    for s, a in refs:
        row = qe[primary][(s, a)]
        uthmani = row["arabic_text"]
        simple = tanzil["simple-clean"][(s, a)]
        uthmani_tanzil = tanzil["uthmani"][(s, a)]
        if a == 1 and s not in (1, 9):
            if not simple.startswith(basmala_simple + " "):
                failures.append(f"{s}:1 simple-clean lacks the expected Basmala header")
            else:
                simple = simple[len(basmala_simple) + 1 :]
                headers_removed.append(s)
            # the header is the first four words; 95:1 and 97:1 write it with a shadda on the ba (بِّسْمِ)
            words = uthmani_tanzil.split(" ")
            if normalize_ns(" ".join(words[:4])) != normalize_ns(basmala_uthmani):
                failures.append(f"{s}:1 Tanzil uthmani lacks the expected Basmala header")
            else:
                uthmani_tanzil = " ".join(words[4:])
        if not uthmani.strip() or not simple.strip():
            empty.append(f"{s}:{a}")
        translations = {}
        for k, info in TRANSLATIONS.items():
            r = qe[k][(s, a)]
            if not (r.get("translation") or "").strip():
                empty.append(f"{k}:{s}:{a}")
            translations[k] = TranslationText(
                lang=info["lang"],
                text=r["translation"],
                footnotes=r.get("footnotes") or None,
                version=listed.get(k, {}).get("version"),
            )
        tafsir = {}
        for k, info in TAFSIR.items():
            r = qe[k][(s, a)]
            if not (r.get("translation") or "").strip():
                empty.append(f"{k}:{s}:{a}")
            tafsir[k] = TranslationText(
                lang=info["lang"], text=r["translation"], version=listed.get(k, {}).get("version")
            )
        m = suras[s]
        records.append(
            QuranRecord(
                id=f"q:{s}:{a}",
                sura=s,
                aya=a,
                text_uthmani=uthmani,
                text_uthmani_tanzil=uthmani_tanzil,
                text_simple=simple,
                text_norm=normalize(simple),
                text_norm_ns=normalize_ns(simple),
                sura_name_ar=m["name"],
                sura_name_en=m["tname"],
                sura_name_en_meaning=m["ename"],
                juz=juz_of(s, a, juz_starts),
                revelation="meccan" if m["type"] == "Meccan" else "medinan",
                translations=translations,
                tafsir=tafsir,
                audio={"alafasy": AUDIO_ALAFASY.format(sura=s, aya=a)},
            )
        )
    checks["basmala_header_separated_from_aya1"] = {
        "suras": len(headers_removed),
        "note": "Tanzil header, not verse text",
    }
    if len(headers_removed) != EXPECTED_SURAS - 2:
        failures.append(f"Basmala header separated from {len(headers_removed)} suras, expected 112")
    # the matching text of aya 1 must now agree with QuranEnc's Uthmani on its first word (catches header leftovers)
    first_word_diff = [
        f"{r.sura}:1"
        for r in records
        if r.aya == 1 and normalize_ns(r.text_simple)[:2] != normalize_ns(r.text_uthmani)[:2]
    ]
    checks["aya1_first_letters_match_uthmani"] = not first_word_diff
    if first_word_diff:
        failures.append(f"aya 1 simple/uthmani start differs at {first_word_diff[:10]}")
    checks["empty_texts"] = empty
    if empty:
        failures.append(f"{len(empty)} empty texts, e.g. {empty[:10]}")

    # text_uthmani must equal the decoded source response exactly (re-read from the cached raw bytes)
    raw_primary = {}
    for s in range(1, EXPECTED_SURAS + 1):
        for row in json.loads((raw_dir / "quranenc" / primary / f"{s:03d}.json").read_bytes())["result"]:
            raw_primary[(int(row["sura"]), int(row["aya"]))] = row["arabic_text"]
    not_identical = [r.id for r in records if r.text_uthmani.encode() != raw_primary[(r.sura, r.aya)].encode()]
    checks["text_uthmani_byte_identical_to_source"] = not not_identical
    if not_identical:
        failures.append(f"text_uthmani not byte-identical at {not_identical[:10]}")

    # juz sanity: 30 juz, monotonic
    juz_values = [r.juz for r in records]
    checks["juz_range"] = [min(juz_values), max(juz_values)]
    if juz_values != sorted(juz_values) or set(juz_values) != set(range(1, 31)):
        failures.append("juz assignment not monotonic 1..30")

    # cross-check QuranEnc Uthmani vs Tanzil Uthmani after normalisation. Tanzil prefixes the Basmala to aya 1
    # of every sura except 1 and 9; QuranEnc does not. Any other difference fails the build.
    basmala_ns = normalize_ns(tanzil["simple-clean"][(1, 1)])

    def tanzil_uthmani_ns(s: int, a: int) -> str:
        t = normalize_ns(tanzil["uthmani"][(s, a)])
        return t.removeprefix(basmala_ns) if a == 1 and s not in (1, 9) else t

    xdiff = [
        f"{s}:{a}" for (s, a) in refs if normalize_ns(qe[primary][(s, a)]["arabic_text"]) != tanzil_uthmani_ns(s, a)
    ]
    checks["uthmani_crosscheck_tanzil"] = {"agree": len(refs) - len(xdiff), "differ": len(xdiff), "differ_refs": xdiff}
    if xdiff:
        failures.append(f"QuranEnc and Tanzil Uthmani differ (normalised) at {xdiff[:10]}")

    if failures:
        raise BuildError("corpus build checks failed:\n  - " + "\n  - ".join(failures))

    out_dir = data / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    body = "".join(r.model_dump_json() + "\n" for r in records).encode("utf-8")
    (out_dir / "quran.jsonl").write_bytes(body)
    manifest["outputs"]["quran.jsonl"] = {"records": len(records), "sha256": sha256(body)}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--offline", action="store_true", help="use cached raw files only")
    args = p.parse_args()
    m = build(args.data, args.offline)
    x = m["checks"]["uthmani_crosscheck_tanzil"]
    print(f"OK: {m['outputs']['quran.jsonl']['records']} ayahs · juz {m['checks']['juz_range']}")
    print(f"QuranEnc vs Tanzil Uthmani (normalised): {x['agree']} agree, {x['differ']} differ")


if __name__ == "__main__":
    main()
