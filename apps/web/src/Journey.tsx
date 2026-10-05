/* The learning journey around a verse card (Track 03): guess before reading, why the match is sure, where the
   verse sits in the Quran, the next stops, a short understanding check and the visitor's discovery passport.
   Everything shown comes from approved data via the API; quiz results are sent as anonymous counts. */
import { useContext, useEffect, useMemo, useState } from "react";
import {
  journey as getJourney, postQuiz, quiz as getQuiz, quranMap,
  type Card, type Journey, type Quiz, type QuizOption, type SurahInfo,
} from "./api";
import { I18nContext, arabicDigits, useT } from "./i18n";

const useNum = () => {
  const { lang } = useContext(I18nContext);
  return (n: number | string) => (lang === "ar" ? arabicDigits(n) : String(n));
};

/* ---------- discovery passport (this browser only) ---------- */
const PASSPORT_KEY = "nun-passport";
export const TOTAL_PANELS = 18;
export function readPassport(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(PASSPORT_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}
export function stamp(id: string): string[] {
  const list = readPassport();
  if (!list.includes(id)) list.push(id);
  try {
    localStorage.setItem(PASSPORT_KEY, JSON.stringify(list));
  } catch {
    /* storage unavailable: the passport just isn't kept */
  }
  return list;
}

export function Passport({ ids }: { ids: string[] }) {
  const t = useT();
  const num = useNum();
  const shown = ids.filter((id) => !id.startsWith("real_"));
  if (!shown.length) return null;
  return (
    <div className="passport">
      <div className="passport-head">
        <b>{t("passport.title")}</b>
        <span>{t("passport.count").replace("{n}", num(shown.length)).replace("{t}", num(TOTAL_PANELS))}</span>
      </div>
      <div className="passport-bar"><i style={{ width: `${(100 * shown.length) / TOTAL_PANELS}%` }} /></div>
      <div className="passport-stamps">
        {shown.map((id) => <img key={id} src={`/panels/${id}.jpg`} alt="" />)}
      </div>
    </div>
  );
}

/* ---------- guess the meaning before reading ---------- */
export function PreGuess({ quiz, onDone }: { quiz: Quiz | null; onDone: (correct: boolean | null) => void }) {
  const t = useT();
  const q = quiz?.questions.find((x) => x.id === "meaning");
  if (!q) return null;
  return (
    <div className="pre-guess">
      <div className="pre-head">
        <span className="pre-icon">؟</span>
        <div>
          <b>{t("guess.title")}</b>
          <span>{t("guess.sub")}</span>
        </div>
      </div>
      <div className="options">
        {q.options.map((o, i) => (
          <button key={i} className="option" dir="ltr" onClick={() => onDone(o.correct)}>
            {(o.text ?? "").replace(/\[\d+\]/g, "")}
          </button>
        ))}
      </div>
      <button className="skip" onClick={() => onDone(null)}>{t("guess.skip")}</button>
    </div>
  );
}

/* ---------- why we're sure: verified point pairs, reference ↔ visitor photo ---------- */
export function WhySure({ photo, reference, pairs, inliers, coverage }: {
  photo: string; reference: string | null; pairs: number[][] | null; inliers: number; coverage: number;
}) {
  const t = useT();
  const num = useNum();
  const [open, setOpen] = useState(false);
  const [ratio, setRatio] = useState<[number, number]>([1, 1]);
  return (
    <div className={`why ${open ? "open" : ""}`}>
      <button className="why-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="why-icon">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
        </span>
        <span className="why-title">
          <b>{t("why.title")}</b>
          <span>{t("why.stats").replace("{n}", num(inliers.toLocaleString("en"))).replace("{c}", num(Math.round(coverage * 100)))}</span>
        </span>
        <span className="chev">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="why-body">
          {reference && pairs ? (
            <div className="match-viz" dir="ltr">
              <div className="mv-img"><img src={reference} alt="" onLoad={(e) => {
                const r0 = e.currentTarget.naturalWidth / e.currentTarget.naturalHeight; // read now: currentTarget is cleared after the handler
                setRatio((r) => [r0, r[1]]);
              }} /><span>{t("why.reference")}</span></div>
              <div className="mv-img"><img src={photo} alt="" onLoad={(e) => {
                const r1 = e.currentTarget.naturalWidth / e.currentTarget.naturalHeight;
                setRatio((r) => [r[0], r1]);
              }} /><span>{t("why.yours")}</span></div>
              <MatchLines pairs={pairs} ratio={ratio} />
            </div>
          ) : (
            <img className="mv-single" src={photo} alt="" />
          )}
          <p className="why-text">{t("why.explain")}</p>
        </div>
      )}
    </div>
  );
}

/** Lines between the two images (each drawn with object-fit: contain in a square box). */
function MatchLines({ pairs, ratio }: { pairs: number[][]; ratio: [number, number] }) {
  // map a fraction inside an image of aspect r, drawn "contain" in a 1×1 box placed at x offset ox (box width 1)
  const place = (fx: number, fy: number, r: number, ox: number) => {
    const w = r >= 1 ? 1 : r;
    const h = r >= 1 ? 1 / r : 1;
    return [ox + (1 - w) / 2 + fx * w, (1 - h) / 2 + fy * h];
  };
  return (
    <svg className="mv-lines" viewBox="0 0 2.08 1" preserveAspectRatio="none" aria-hidden="true">
      {pairs.map(([qx, qy, rx, ry], i) => {
        const [x1, y1] = place(rx!, ry!, ratio[0], 0);
        const [x2, y2] = place(qx!, qy!, ratio[1], 1.08);
        return (
          <g key={i} style={{ animationDelay: `${i * 18}ms` }}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} vectorEffect="non-scaling-stroke" />
            <circle cx={x1} cy={y1} r={0.008} /><circle cx={x2} cy={y2} r={0.008} />
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- where in the Quran ---------- */
let mapCache: SurahInfo[] | null = null;
export function QuranMap({ card }: { card: Card }) {
  const t = useT();
  const num = useNum();
  const { lang } = useContext(I18nContext);
  const [map, setMap] = useState<SurahInfo[] | null>(mapCache);
  useEffect(() => {
    if (mapCache) return;
    quranMap().then((m) => { mapCache = m; setMap(m); }).catch(() => undefined);
  }, []);
  if (!map) return null;
  const me = map.find((s) => s.sura === card.ref.sura);
  const max = Math.max(...map.map((s) => s.ayahs));
  return (
    <div className="qmap">
      <div className="qmap-head">
        <b>{t("map.title")}</b>
        <span>
          {t("map.where").replace("{s}", lang === "ar" ? me?.ar ?? "" : me?.en ?? "").replace("{n}", num(card.ref.sura))
            .replace("{a}", num(me?.ayahs ?? 0)).replace("{j}", num(card.juz))}
        </span>
      </div>
      <div className="qmap-bars" dir="rtl" role="img" aria-label={t("map.title")}>
        {map.map((s) => (
          <i
            key={s.sura}
            className={`${s.revelation} ${s.sura === card.ref.sura ? "me" : ""}`}
            style={{ height: `${12 + 88 * Math.sqrt(s.ayahs / max)}%` }}
            title={`${s.sura}. ${lang === "ar" ? s.ar : s.en} (${s.ayahs})`}
          />
        ))}
      </div>
      <div className="qmap-legend">
        <span><i className="meccan" />{t("card.meccan")}</span>
        <span><i className="medinan" />{t("card.medinan")}</span>
        <span><i className="me" />{lang === "ar" ? me?.ar : me?.en}</span>
      </div>
      <div className="juz-strip" dir="rtl">
        {Array.from({ length: 30 }, (_, i) => (
          <i key={i} className={i + 1 === card.juz ? "me" : i + 1 < card.juz ? "past" : ""}>{i + 1 === card.juz ? num(card.juz) : ""}</i>
        ))}
      </div>
      <span className="juz-label">{t("map.juz")}</span>
    </div>
  );
}

/* ---------- context + next stops ---------- */
export function JourneyView({ card, panelId, onScan }: { card: Card; panelId?: string; onScan: (src: string) => void }) {
  const t = useT();
  const num = useNum();
  const { lang } = useContext(I18nContext);
  const [j, setJ] = useState<Journey | null>(null);
  useEffect(() => {
    let live = true;
    getJourney(card, lang, panelId).then((x) => live && setJ(x)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [card, lang, panelId]);
  if (!j) return null;
  const relation = (r: string) => t(r === "next" ? "journey.nextPanel" : r === "before" ? "journey.prevPanel" : "journey.samePanel");
  return (
    <div className="journey">
      <h3>{t("journey.title")}</h3>
      <div className="context">
        {j.prev && <ContextAyah a={j.prev} label={t("journey.before")} />}
        <div className="ctx-now"><span>{t("journey.now")}</span><b>{card.ref.label}</b></div>
        {j.next && <ContextAyah a={j.next} label={t("journey.after")} />}
      </div>
      {j.stops.length > 0 && (
        <div className="stops">
          {j.stops.map((s) => (
            <button key={s.id} className="stop" onClick={() => onScan(s.image)}>
              <img src={s.image} alt="" />
              <span className="stop-text">
                <small>{relation(s.relation)}</small>
                <b>{num(s.sura)}:{num(s.aya_from)}</b>
                <span className="stop-go">{t("journey.go")}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      {j.stops.length === 0 && <p className="muted small">{t("journey.noStops")}</p>}
    </div>
  );
}

function ContextAyah({ a, label }: { a: { label: string; text_display: string; translation: string | null }; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <button className={`ctx ${open ? "open" : ""}`} onClick={() => setOpen(!open)}>
      <span className="ctx-label">{label} · {a.label}</span>
      <span className="quran ctx-text" dir="rtl" lang="ar">{a.text_display}</span>
      {open && a.translation && <span className="ctx-tr" dir="ltr">“{a.translation.replace(/\[\d+\]/g, "").trim()}”</span>}
    </button>
  );
}

/* ---------- understanding check ---------- */
export function QuizView({ card, quiz, pre, panelId }: { card: Card; quiz: Quiz | null; pre: boolean | null; panelId?: string }) {
  const t = useT();
  const num = useNum();
  const { lang } = useContext(I18nContext);
  const [open, setOpen] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [sent, setSent] = useState(false);
  const qs = quiz?.questions ?? [];
  const done = qs.length > 0 && qs.every((q) => answers[q.id] !== undefined);
  const score = useMemo(() => qs.filter((q) => q.options[answers[q.id] ?? -1]?.correct).length, [qs, answers]);
  useEffect(() => {
    if (done && !sent) {
      setSent(true);
      void postQuiz({ panel: panelId, sura: card.ref.sura, aya: card.ref.aya_from, lang, pre_correct: pre, post_correct: score, post_total: qs.length });
    }
  }, [done, sent, panelId, card, lang, pre, score, qs.length]);
  if (!quiz) return null;
  const label = (q: string, o: QuizOption) =>
    q === "surah" ? (lang === "ar" ? o.ar : o.en) : q === "revelation" ? t(o.key === "meccan" ? "card.meccan" : "card.medinan") : (o.text ?? "").replace(/\[\d+\]/g, "");
  if (!open) {
    return (
      <button className="quiz-cta" onClick={() => setOpen(true)}>
        <span className="quiz-badge">✓✗</span>
        <span><b>{t("quiz.cta")}</b><small>{t("quiz.ctaSub")}</small></span>
      </button>
    );
  }
  return (
    <div className="quiz">
      <h3>{t("quiz.cta")}</h3>
      {qs.map((q, qi) => (
        <div key={q.id} className="quiz-q">
          <p><span className="qn">{num(qi + 1)}</span>{t(`quiz.${q.id}` as Parameters<typeof t>[0])}</p>
          <div className="options">
            {q.options.map((o, i) => {
              const chosen = answers[q.id] === i;
              const reveal = answers[q.id] !== undefined;
              return (
                <button
                  key={i}
                  dir={q.id === "meaning" ? "ltr" : undefined}
                  className={`option ${reveal && o.correct ? "right" : ""} ${chosen && !o.correct ? "wrong" : ""}`}
                  disabled={reveal}
                  onClick={() => setAnswers((a) => ({ ...a, [q.id]: i }))}
                >
                  {label(q.id, o)}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {done && (
        <div className="quiz-result">
          <b>{t("quiz.score").replace("{s}", num(score)).replace("{t}", num(qs.length))}</b>
          {pre !== null && <span>{pre ? t("quiz.preRight") : t("quiz.preWrong")}</span>}
          <small>{t("quiz.privacy")}</small>
        </div>
      )}
    </div>
  );
}

export { getQuiz };
