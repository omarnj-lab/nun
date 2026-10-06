import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { ask, regions, scan, shrink, type Card, type ChatReply, type Citation, type Quiz, type Reading, type Region, type Regions, type Seen, type Turn } from "./api";
import { I18nContext, arabicDigits, dirOf, useT, type Key, type Lang } from "./i18n";
import { Explore, PreGuess, getQuiz, readPassport, stamp } from "./Journey";
import { Lab } from "./Lab";

type Matched = {
  photo: string;
  upload: Blob;
  card: Card;
  polygon: number[][] | null;
  panelId: string; // "" when the verse came from the reading path
  source: "match" | "read";
  reading: Reading | null;
  pairs: number[][] | null;
  reference: string | null;
  inliers: number;
  coverage: number;
};

/** Photo → match → view. Used by the landing page, the gallery and the journey's "next stop" buttons. */
async function runScan(file: Blob, lang: string, onView: (v: View) => void) {
  const photo = URL.createObjectURL(file); // stays in the browser; only a downscaled copy is sent
  onView({ name: "scanning", photo });
  try {
    const upload = await shrink(file);
    const r = await scan(upload, lang);
    onView(
      r.status === "matched"
        ? {
            name: "result", chat: false, photo, upload, card: r.card, polygon: r.panel.polygon ?? null,
            panelId: r.panel.id, source: "match", reading: null, pairs: r.panel.pairs ?? null, reference: r.panel.reference ?? null,
            inliers: r.panel.inliers, coverage: r.panel.coverage,
          }
        : r.status === "read"
          ? {
              name: "result", chat: false, photo, upload, card: r.card, polygon: null, panelId: "", source: "read",
              reading: r.reading, pairs: null, reference: null, inliers: 0, coverage: 0,
            }
          : { name: "uncertain", photo, notQuranic: r.status === "not_quranic", reason: r.reason, seen: r.seen ?? null },
    );
  } catch (err) {
    onView({ name: "error", message: (err as Error).message });
  }
}
type View =
  | { name: "home" }
  | { name: "scanning"; photo: string }
  | ({ name: "result"; chat: boolean } & Matched)
  | { name: "uncertain"; photo: string; notQuranic: boolean; reason?: string; seen: Seen | null }
  | { name: "error"; message: string }
  | { name: "lab" };

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("nun-lang");
    if (saved === "ar" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  return "ar";
}

const useLang = () => useContext(I18nContext);

export default function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dirOf(lang);
    try {
      localStorage.setItem("nun-lang", lang);
    } catch {
      /* ignore */
    }
  }, [lang]);
  return (
    <I18nContext.Provider value={{ lang, setLang }}>
      <Shell />
    </I18nContext.Provider>
  );
}

function Shell() {
  const t = useT();
  const [view, setView] = useState<View>({ name: "home" });
  const home = () => setView({ name: "home" });
  return (
    <div className={`app ${view.name === "result" || view.name === "home" || view.name === "lab" ? "wide" : ""} view-${view.name}`}>
      <Header onHome={home} onLab={() => { window.scrollTo({ top: 0 }); setView({ name: "lab" }); }} />
      <main className="main">
        {view.name === "home" && <Home onView={setView} />}
        {view.name === "lab" && <Lab onBack={home} />}
        {view.name === "scanning" && <Scanning photo={view.photo} />}
        {view.name === "result" && (
          <Workspace key={view.photo} view={view} setChat={(chat) => setView({ ...view, chat })} onAgain={home} onView={setView} />
        )}
        {view.name === "uncertain" && <Uncertain view={view} onAgain={home} />}
        {view.name === "error" && (
          <section className="sheet narrow">
            <h2>{t("error.title")}</h2>
            <p>{view.message}</p>
            <button className="btn primary" onClick={home}>{t("scan.again")}</button>
          </section>
        )}
      </main>
      <footer className="footer">{t("footer.ai")}</footer>
    </div>
  );
}

function Header({ onHome, onLab }: { onHome: () => void; onLab: () => void }) {
  const t = useT();
  const { lang, setLang } = useLang();
  return (
    <header className="header">
      <button className="logo-btn" onClick={onHome} aria-label={t("app.name")}>
        <img src="/logo.svg" alt={t("app.name")} className="logo" />
      </button>
      <div className="header-actions">
        <button className="lab-link" onClick={onLab}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3" /><path d="M7 15h10" /></svg>
          {t("lab.open")}
        </button>
        <button className="btn ghost" onClick={() => setLang(lang === "ar" ? "en" : "ar")}>{t("lang.switch")}</button>
      </div>
    </header>
  );
}

const PANELS = [
  "02_ivory_blue", "03_navy_gold", "07_teal_silver", "09_burgundy_gold", "15_forest_gold", "05_lapis_illumination",
  "21_peacock_gold", "13_plum_pearl", "24_midnight_gold", "04_rose_parchment", "12_indigo_copper", "17_white_gold",
  "22_wine_ivory", "11_cobalt_white", "16_turquoise_cream", "23_mint_blue", "19_charcoal_silver", "08_sage_cream",
];
const panelSrc = (id: string) => `/panels/${id}.jpg`;

const Icon = {
  camera: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>
  ),
  upload: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M5 15v4h14v-4" /></svg>
  ),
  verify: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
  ),
  chat: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v10H10l-4 4v-4H5z" /><path d="M9 10h6" /></svg>
  ),
  book: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5c3-1 5.5-.5 8 1.5C14.5 4.5 17 4 20 5v13c-3-1-5.5-.5-8 1.5C9.5 17.5 7 17 4 18z" /><path d="M12 6.5v13" /></svg>
  ),
  wave: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" /></svg>
  ),
  lock: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
  ),
};

/** The hero's verse comes from the corpus through the API (never typed into the UI). */
function HeroVerse() {
  const { lang } = useLang();
  const [v, setV] = useState<{ text: string; ref: string } | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`/api/verse/68/1?lang=${lang}`)
      .then((r) => (r.ok ? (r.json() as Promise<Card>) : null))
      .then((c) => {
        if (live && c?.ayahs[0]) {
          const name = lang === "ar" ? c.sura_name.ar : c.sura_name.en;
          setV({ text: c.ayahs[0].text_display, ref: `${name} : ${lang === "ar" ? arabicDigits(1) : 1}` });
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [lang]);
  if (!v) return <div className="hero-verse placeholder" />;
  return (
    <p className="hero-verse">
      <span className="quran" dir="rtl" lang="ar">﴿{v.text}﴾</span>
      <span className="hero-verse-ref">{v.ref}</span>
    </p>
  );
}

function Home({ onView }: { onView: (v: View) => void }) {
  const t = useT();
  const { lang } = useLang();
  const run = (file: Blob) => runScan(file, lang, onView);
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) void run(file);
  };
  const marquee = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // the gallery animates only while it is on screen
    const el = marquee.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(([e]) => el.classList.toggle("paused", !e!.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const tryImage = async (src: string) => {
    const blob = await (await fetch(src)).blob();
    void run(blob);
  };
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-text">
          <span className="track-pill">{t("hero.track")}</span>
          <img src="/logo.svg" alt={t("app.name")} className="hero-logo" />
          <h1 className="hero-title">
            {t("hero.h1a")}<em>{t("hero.h1b")}</em>{t("hero.h1c")}
          </h1>
          <HeroVerse />
          <p className="hero-lead">{t("hero.lead")}</p>
          <div className="cta-row">
            <label className="cta primary">
              {Icon.camera}
              <span>{t("hero.camera")}</span>
              <input type="file" accept="image/*" capture="environment" hidden onChange={onPick} />
            </label>
            <label className="cta">
              {Icon.upload}
              <span>{t("hero.upload")}</span>
              <input type="file" accept="image/*" hidden onChange={onPick} />
            </label>
          </div>
          <button className="sample-link" onClick={() => void tryImage("/sample.jpg")}>
            <img src={panelSrc("02_ivory_blue")} alt="" /> {t("hero.sample")} {lang === "ar" ? "←" : "→"}
          </button>
        </div>
        <div className="collage" aria-hidden="true">
          <img className="card c-back" src={panelSrc("03_navy_gold")} alt="" />
          <img className="card c-mid" src={panelSrc("07_teal_silver")} alt="" />
          <div className="card c-front">
            <img src={panelSrc("02_ivory_blue")} alt="" />
            <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
            <div className="scan-line" />
          </div>
          <div className="result-chip">
            <span className="tick">✓</span>
            <span><b>{t("hero.previewOk")}</b><small>{t("hero.previewRef")}</small></span>
          </div>
        </div>
      </section>

      <ul className="trust">
        <li>{Icon.book}<span>{t("trust.text")}</span></li>
        <li>{Icon.wave}<span>{t("trust.voice")}</span></li>
        <li>{Icon.lock}<span>{t("trust.privacy")}</span></li>
      </ul>

      <section className="steps">
        <h2>{t("steps.title")}</h2>
        <ol>
          {([["1", Icon.camera], ["2", Icon.verify], ["3", Icon.chat]] as const).map(([n, icon]) => (
            <li key={n}>
              <span className="step-icon">{icon}</span>
              <span className="step-no">{lang === "ar" ? arabicDigits(n) : n}</span>
              <h3>{t(`steps.${n}t` as Key)}</h3>
              <p>{t(`steps.${n}d` as Key)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="gallery">
        <h2>{t("gallery.title")}</h2>
        <p>{t("gallery.sub")}</p>
        <div className="marquee" dir="ltr" ref={marquee}>
          <div className="marquee-track">
            {[...PANELS, ...PANELS].map((id, i) => (
              <button
                key={i}
                className="gallery-item"
                onClick={() => void tryImage(panelSrc(id))}
                aria-label={t("gallery.try")}
                tabIndex={i < PANELS.length ? 0 : -1}
                aria-hidden={i >= PANELS.length}
              >
                <img src={panelSrc(id)} alt="" loading="lazy" />
                <span className="gallery-cta">{Icon.camera}{t("gallery.try")}</span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Scanning({ photo }: { photo: string }) {
  const t = useT();
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, 3)), 1100);
    return () => window.clearInterval(id);
  }, []);
  return (
    <section className="scanning">
      <div className="viewfinder live">
        <span className="pill">{t("scan.pill")}</span>
        <img src={photo} alt="" />
        <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
        <div className="scan-line" />
      </div>
      <ol className="scan-steps">
        {(["scan.step1", "scan.step2", "scan.step3", "scan.step4"] as const).filter((_, i) => i < 3 || step >= 3).map((k, i) => (
          <li key={k} className={i < step ? "done" : i === step ? "now" : ""}>
            <span className="dot">{i < step ? "✓" : ""}</span>{t(k)}
          </li>
        ))}
      </ol>
    </section>
  );
}

const THEME_KEY: Record<string, Key> = {
  "names of Allah": "theme.names_allah", "devotional invocation": "theme.dua", hadith: "theme.hadith",
  "names of the Prophet": "theme.prophet", "names of companions": "theme.companions", dedication: "theme.dedication",
  "personal/place name": "theme.name", "non-religious": "theme.non_religious", quranic: "theme.quranic",
};

/** No verse shown: either KhaṭṭVision judged the panel not Quranic, or the reading was not safe to trust.
 *  The visitor still sees what our model saw (style, where the text is), never a guessed verse. */
function Uncertain({ view, onAgain }: {
  view: { photo: string; notQuranic: boolean; reason?: string; seen: Seen | null };
  onAgain: () => void;
}) {
  const t = useT();
  const { lang } = useLang();
  const seen = view.seen;
  const style = seen?.styles[0];
  const styleName = style ? (lang === "ar" ? STYLE_AR[style] ?? style : style) : null;
  const regs: Region[] = (seen?.boxes ?? []).map((box) => ({ box, words: [] }));
  const theme = seen?.theme ? THEME_KEY[seen.theme] : undefined;
  return (
    <section className="sheet narrow">
      {regs.length ? <PhotoWithRegions photo={view.photo} polygon={null} regs={regs} active={null} onPick={() => undefined} />
        : <img src={view.photo} alt="" className="photo" />}
      {seen && (
        <div className="seen">
          <span className="seen-title">{t("seen.title")}</span>
          <div className="chips">
            {styleName && <span className="chip style">{t("card.style")} {styleName}</span>}
            {theme && <span className={`chip ${view.notQuranic ? "" : "ok"}`}>{t(theme)}</span>}
            {regs.length > 0 && <span className="chip">{t("seen.regions").replace("{n}", lang === "ar" ? arabicDigits(regs.length) : String(regs.length))}</span>}
          </div>
        </div>
      )}
      <div className={`notice ${view.notQuranic ? "info-note" : "warn"}`}>
        <span className={`badge ${view.notQuranic ? "" : "warn"}`}>{view.notQuranic ? t("notq.badge") : t("uncertain.badge")}</span>
        <h2>{view.notQuranic ? t("notq.title") : t("uncertain.title")}</h2>
        <p>
          {view.notQuranic ? t("notq.body")
            : view.reason === "ornate_style" ? t("uncertain.ornate").replace("{s}", styleName ?? "")
            : t("uncertain.body")}
        </p>
        {!view.notQuranic && <p className="muted">{t("uncertain.tips")}</p>}
        <p className="muted">{t("uncertain.guide")}</p>
      </div>
      <button className="btn primary" onClick={onAgain}>{t("scan.again")}</button>
    </section>
  );
}

const WIDE = "(min-width: 960px)";

/** Desktop: verse info and chat side by side (info on the reading-start side). Phone: info, then chat. */
function Workspace({ view, setChat, onAgain, onView }: {
  view: Matched & { chat: boolean };
  setChat: (c: boolean) => void;
  onAgain: () => void;
  onView: (v: View) => void;
}) {
  const { lang } = useLang();
  const onScan = (src: string) => {
    window.scrollTo({ top: 0 });
    void fetch(src).then((r) => r.blob()).then((b) => runScan(b, lang, onView));
  };
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  useEffect(() => {
    const mq = window.matchMedia(WIDE);
    const on = () => setWide(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  if (wide) {
    return (
      <div className="workspace">
        <Info view={view} onAsk={null} onAgain={onAgain} onScan={onScan} />
        <Chat view={view} onBack={null} />
      </div>
    );
  }
  return view.chat ? (
    <Chat view={view} onBack={() => setChat(false)} />
  ) : (
    <Info view={view} onAsk={() => setChat(true)} onAgain={onAgain} onScan={onScan} />
  );
}

const wordKey = (aya: number, i: number) => `${aya}:${i}`;

/** The visitor's photo: the matched panel's boundary (matcher homography) in gold, and KhaṭṭVision's text regions.
 *  Tapping a region lights up its words in the verse; tapping a word lights up its region. */
function PhotoWithRegions({ photo, polygon, regs, active, onPick, singing = -1 }: {
  photo: string;
  polygon: number[][] | null;
  regs: Region[];
  active: number | null;
  onPick: (i: number | null) => void;
  singing?: number;
}) {
  const t = useT();
  const { lang } = useLang();
  return (
    <figure className="photo-box">
      <div className="photo-frame">
        <img src={photo} alt="" />
        <svg viewBox="0 0 1 1" preserveAspectRatio="none">
          {polygon && (
            <polygon className="panel-outline" points={polygon.map((p) => p.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />
          )}
          {regs.map((r, i) => (
            <rect
              key={i}
              className={`region ${active === i ? "on" : ""} ${singing === i ? "singing" : ""} ${r.words.length ? "" : "no-words"}`}
              x={r.box[0]} y={r.box[1]} width={r.box[2] - r.box[0]} height={r.box[3] - r.box[1]}
              vectorEffect="non-scaling-stroke"
              role="button"
              aria-label={`${t("regions.region")} ${i + 1}`}
              onClick={() => onPick(active === i ? null : i)}
            />
          ))}
        </svg>
        {regs.map((r, i) => (
          <span
            key={i}
            className={`region-badge ${active === i ? "on" : ""}`}
            style={{ left: `${r.box[0] * 100}%`, top: `${r.box[1] * 100}%` }}
            onClick={() => onPick(active === i ? null : i)}
          >
            {lang === "ar" ? arabicDigits(i + 1) : i + 1}
          </span>
        ))}
      </div>
    </figure>
  );
}

const STYLE_AR: Record<string, string> = {
  Thuluth: "الثلث", Diwani: "الديواني", Naskh: "النسخ", Kufic: "الكوفي", "Ruq'ah": "الرقعة", "Nasta'liq": "النستعليق",
};

function Info({ view, onAsk, onAgain, onScan }: {
  view: Matched;
  onAsk: (() => void) | null;
  onAgain: () => void;
  onScan: (src: string) => void;
}) {
  const t = useT();
  const { lang } = useLang();
  const { card } = view;
  const num = (n: number) => (lang === "ar" ? arabicDigits(n) : String(n));
  const ref = card.ref;
  const ayahs = ref.aya_to !== ref.aya_from ? `${num(ref.aya_from)}–${num(ref.aya_to)}` : num(ref.aya_from);

  const [regs, setRegs] = useState<Regions | "loading">("loading");
  const [active, setActive] = useState<number | null>(null);
  const [tick, setTick] = useState<{ aya: number; frac: number } | null>(null);
  const playingAya = tick?.aya ?? null;
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [pre, setPre] = useState<boolean | null | undefined>(undefined); // undefined = not answered yet
  const [passport, setPassport] = useState<string[]>([]);
  useEffect(() => {
    setPassport(view.panelId ? stamp(view.panelId) : readPassport());
    let live = true;
    getQuiz(card).then((q) => live && setQuiz(q)).catch(() => live && setPre(null));
    return () => {
      live = false;
    };
  }, [card, view.panelId]);
  useEffect(() => {
    if (view.reading) {
      // the reading path already ran KhaṭṭVision: its regions come with the scan
      setRegs({ available: true, styles: view.reading.styles, regions: view.reading.regions, seconds: 0 });
      return;
    }
    let live = true;
    regions(view.upload, card)
      .then((r) => live && setRegs(r))
      .catch(() => live && setRegs({ available: false }));
    return () => {
      live = false;
    };
  }, [view.upload, view.reading, card]);
  const list = regs !== "loading" && regs.available ? regs.regions : [];
  const style = regs !== "loading" && regs.available ? regs.styles[0] : undefined;
  const lit = new Set((active !== null ? list[active]?.words ?? [] : []).map(([a, i]) => wordKey(a, i)));
  const sung = useMemo(() => {
    if (!tick) return null;
    const a = card.ayahs.find((x) => x.aya === tick.aya);
    if (!a) return null;
    const words = a.text_display.split(" ").map((w, i) => ({ i, n: w.replace(/[^\u0621-\u064a]/g, "").length }));
    const total = words.reduce((s, w) => s + w.n, 0) || 1;
    const f = Math.min(1, Math.max(0, (tick.frac - 0.04) / 0.92)); // short silence at both ends of each file
    let acc = 0;
    for (const w of words) {
      acc += w.n / total;
      if (w.n && f <= acc) return w.i;
    }
    return words.length - 1;
  }, [tick, card]);
  const sungKey = tick && sung !== null ? wordKey(tick.aya, sung) : null;
  // which photo region holds each recited word: the model's own alignment when its regions hold different words;
  // when they overlap (it labelled several lines with the whole verse), the verse is spread over the lines in reading
  // order (top to bottom, right to left), in proportion to each line's width
  const wordRegion = useMemo(() => {
    const m = new Map<string, number>();
    const withWords = list.map((r, i) => ({ r, i })).filter(({ r }) => r.words.length);
    const keys = withWords.flatMap(({ r }) => r.words.map(([a, j]) => wordKey(a, j)));
    const overlapping = keys.length > new Set(keys).size * 1.3;
    const lines = list
      .map((r, i) => ({ i, cy: (r.box[1] + r.box[3]) / 2, cx: (r.box[0] + r.box[2]) / 2, w: r.box[2] - r.box[0], h: r.box[3] - r.box[1] }))
      .filter((l) => l.w > l.h * 1.5) // text lines, not a single large word
      .sort((p, q) => (Math.abs(p.cy - q.cy) > 0.05 ? p.cy - q.cy : q.cx - p.cx));
    const linesWithOwnWords = lines.filter((l) => list[l.i]!.words.length > 0).length;
    if (!overlapping && (lines.length < 2 || linesWithOwnWords === lines.length)) {
      for (const { r, i } of withWords) for (const [a, j] of r.words) if (!m.has(wordKey(a, j))) m.set(wordKey(a, j), i);
      return m;
    }
    const verse = card.ayahs.flatMap((a) =>
      a.text_display.split(" ").map((w, j) => ({ k: wordKey(a.aya, j), n: w.replace(/[^ء-ي]/g, "").length })),
    ).filter((x) => x.n);
    if (!lines.length) return m;
    const totalW = lines.reduce((s2, l) => s2 + l.w, 0);
    const totalN = verse.reduce((s2, x) => s2 + x.n, 0);
    let acc = 0, li = 0, edge = lines[0]!.w / totalW;
    for (const x of verse) {
      acc += x.n / totalN;
      while (acc > edge + 1e-9 && li < lines.length - 1) edge += lines[++li]!.w / totalW;
      m.set(x.k, lines[li]!.i);
    }
    return m;
  }, [list, card]);
  const singing = sungKey ? wordRegion.get(sungKey) ?? -1 : -1;
  const pickWord = (aya: number, i: number) => {
    const k = wordKey(aya, i);
    const hit = list.findIndex((r) => r.words.some(([a, j]) => wordKey(a, j) === k));
    setActive(hit >= 0 && hit !== active ? hit : null);
  };

  return (
    <section className="sheet info">
      <PhotoWithRegions photo={view.photo} polygon={view.polygon} regs={list} active={active} onPick={setActive} singing={singing} />
      {tick && singing >= 0 && <p className="on-panel">{t("karaoke.on")}</p>}
      <div className="vision-line">
        {regs === "loading" && <span className="vision-chip loading"><span className="spark" />{t("regions.loading")}</span>}
        {list.length > 0 && <span className="vision-chip">{t("regions.hint")}</span>}
        <span className="caption">{t("card.flow")}</span>
      </div>
      <div className="chips">
        {view.source === "match" ? (
          <span className="chip ok">✓ {t("card.verified")}</span>
        ) : (
          <span className="chip read">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h7" /><circle cx="18" cy="16" r="3" /></svg>
            {t("card.readBy")}{view.reading!.checked ? ` · ${t("card.checked")}` : ""} · {t("card.readScore").replace("{s}", lang === "ar" ? arabicDigits(Math.round(view.reading!.score)) : String(Math.round(view.reading!.score)))}
          </span>
        )}
        <span className="chip">{t("card.quranic")}</span>
        {style && <span className="chip style">{t("card.style")} {lang === "ar" ? STYLE_AR[style] ?? style : style}</span>}
      </div>
      <div className="quran" dir="rtl" lang="ar">
        {card.ayahs.map((a) => (
          <span key={a.aya} className={playingAya === a.aya ? "reciting" : ""}>
            {a.text_display.split(" ").map((w, i) => (
              <span key={i}>
                <span
                  className={`w ${lit.has(wordKey(a.aya, i)) ? "lit" : ""} ${list.length ? "tappable" : ""} ${sungKey === wordKey(a.aya, i) ? "sung" : ""}`}
                  onClick={list.length ? () => pickWord(a.aya, i) : undefined}
                >
                  {w}
                </span>{" "}
              </span>
            ))}
            <span className="aya-no">﴿{arabicDigits(a.aya)}﴾</span>{" "}
          </span>
        ))}
      </div>
      <Player card={card} onTick={setTick} />
      {pre === undefined && quiz && <PreGuess quiz={quiz} onDone={setPre} />}
      {pre !== undefined && pre !== null && (
        <p className={`guess-feedback ${pre ? "right" : "wrong"}`}>{pre ? t("guess.right") : t("guess.wrong")}</p>
      )}
      {(pre !== undefined || !quiz) && card.translation && (
        <blockquote className="translation reveal" dir="ltr" lang="en">
          {card.ayahs.map((a) => (
            <p key={a.aya} className={playingAya === a.aya ? "reciting" : ""}>
              “{(a.translation ?? "").replace(/\[\d+\]/g, "").trim()}”
            </p>
          ))}
          <cite>{card.translation.translator} · v{card.translation.version} · {card.translation.source}</cite>
        </blockquote>
      )}
      <div className="tiles">
        <Tile label={t("card.surahName")} value={lang === "ar" ? card.sura_name.ar : card.sura_name.en} />
        <Tile label={t("card.ayahNo")} value={`${num(ref.sura)} : ${ayahs}`} />
        <Tile label={t("card.juz")} value={num(card.juz)} />
        <Tile label={t("card.revelation")} value={card.revelation === "meccan" ? t("card.meccan") : t("card.medinan")} />
      </div>
      <Explore
        card={card} panelId={view.panelId} onScan={onScan} quiz={quiz} pre={pre ?? null} passport={passport}
        photo={view.photo} reference={view.reference} pairs={view.pairs} inliers={view.inliers} coverage={view.coverage}
        reading={view.reading}
      />
      <p className="sources-line">
        {t("card.sourcesLine")} · {card.recitation.name} ({card.recitation.source})
        {list.length > 0 && <> · {t("regions.source")}</>}
      </p>
      <button className="btn soft" onClick={onAgain}>{t("scan.again")}</button>
      {onAsk && (
        <div className="ask-bar">
          <button className="btn primary big" onClick={onAsk}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v10H10l-4 4v-4H5z" /></svg>
            {t("card.ask")}
          </button>
        </div>
      )}
    </section>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
    </div>
  );
}

const fmt = (s: number) => (Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00");

/** Human recitation (EveryAyah), ayah after ayah, with a visible seek bar; reports the ayah being recited. */
function Player({ card, onTick }: { card: Card; onTick: (t: { aya: number; frac: number } | null) => void }) {
  const t = useT();
  const { lang } = useLang();
  const audio = useRef<HTMLAudioElement>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [dur, setDur] = useState(0);
  const autoNext = useRef(false);
  const n = card.ayahs.length;
  useEffect(() => {
    const a = audio.current;
    if (a && autoNext.current) void a.play().catch(() => setPlaying(false));
  }, [idx]);
  useEffect(() => {
    onTick(playing ? { aya: card.ayahs[idx]!.aya, frac: dur ? time / dur : 0 } : null);
  }, [playing, idx, card, onTick, time, dur]);
  const toggle = () => {
    const a = audio.current;
    if (!a) return;
    if (a.paused) {
      autoNext.current = true;
      void a.play().catch(() => setPlaying(false));
    } else {
      autoNext.current = false;
      a.pause();
    }
  };
  const ended = () => {
    if (idx + 1 < n) setIdx(idx + 1);
    else {
      autoNext.current = false;
      setPlaying(false);
      setIdx(0);
    }
  };
  const num = (v: number) => (lang === "ar" ? arabicDigits(v) : String(v));
  return (
    <div className={`player ${playing ? "on" : ""}`}>
      <audio
        ref={audio}
        src={card.ayahs[idx]!.audio}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={ended}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
      />
      <button className="play" onClick={toggle} aria-label={playing ? t("card.stop") : t("card.listen")}>
        {playing ? (
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" /></svg>
        )}
      </button>
      <div className="player-body">
        <div className="player-top">
          <b>{t("card.recitation")} · {card.recitation.name}</b>
          <span>
            {n > 1 ? `${t("card.ayah")} ${num(idx + 1)} / ${num(n)} · ` : ""}
            <bdi dir="ltr">{fmt(time)} / {fmt(dur)}</bdi>
          </span>
        </div>
        <input
          type="range" min={0} max={dur || 1} step={0.1} value={time} dir="ltr"
          aria-label={t("card.recitation")}
          style={{ ["--p" as string]: `${dur ? (time / dur) * 100 : 0}%` }}
          onChange={(e) => {
            if (audio.current) audio.current.currentTime = Number(e.target.value);
          }}
        />
        <div className={`bars ${playing ? "live" : ""}`} aria-hidden="true">
          {Array.from({ length: 28 }, (_, i) => <i key={i} style={{ animationDelay: `${(i % 7) * 0.11}s` }} />)}
        </div>
      </div>
    </div>
  );
}

/** What the server is doing while the visitor waits (the pipeline's stages, paced to typical timings). */
function ThinkingSteps() {
  const t = useT();
  const [step, setStep] = useState(0);
  useEffect(() => {
    const a = window.setTimeout(() => setStep(1), 1200);
    const b = window.setTimeout(() => setStep(2), 4800);
    return () => {
      window.clearTimeout(a);
      window.clearTimeout(b);
    };
  }, []);
  return (
    <div className="bubble assistant thinking" aria-live="polite">
      {(["think.sources", "think.writing", "think.checking"] as const).map((k, i) => (
        <span key={k} className={i < step ? "done" : i === step ? "now" : ""}>
          <i>{i < step ? "✓" : ""}</i>{t(k)}
        </span>
      ))}
    </div>
  );
}

type Msg = { role: "user" | "assistant"; text: string; reply?: ChatReply };

function citeLabel(c: Citation, card: Card, t: ReturnType<typeof useT>): string {
  if (c.id === "D1") return t("cite.quran");
  if (/translation/i.test(c.title)) return card.translation?.translator.replace("International", "Intl.") ?? c.source;
  return t("cite.facts");
}

/** Reply languages offered in the picker ("auto" = the language the visitor writes or speaks in). */
const CHAT_LANGS: [code: string, native: string, speech: string][] = [
  ["ar", "العربية", "ar-SA"], ["en", "English", "en-US"], ["fr", "Français", "fr-FR"], ["es", "Español", "es-ES"],
  ["de", "Deutsch", "de-DE"], ["tr", "Türkçe", "tr-TR"], ["ur", "اردو", "ur-PK"], ["fa", "فارسی", "fa-IR"],
  ["id", "Bahasa Indonesia", "id-ID"], ["ms", "Bahasa Melayu", "ms-MY"], ["zh", "中文", "zh-CN"], ["ru", "Русский", "ru-RU"],
  ["bn", "বাংলা", "bn-BD"], ["hi", "हिन्दी", "hi-IN"], ["it", "Italiano", "it-IT"], ["pt", "Português", "pt-BR"],
  ["ja", "日本語", "ja-JP"], ["ko", "한국어", "ko-KR"], ["sw", "Kiswahili", "sw-KE"], ["nl", "Nederlands", "nl-NL"],
];
const speechCode = (code: string) => CHAT_LANGS.find((l) => l[0] === code)?.[2] ?? code;

/** Text for the synthetic voice: generated explanations only. Anything marked as Quran (﴿…﴾) or carrying Quranic
 *  diacritics is left out, so a synthetic voice never recites the Quran (CLAUDE.md rule 2). */
function speakable(text: string): string {
  return text
    .replace(/﴿[^﴾]*﴾/g, " ")
    .split(/\s+/)
    .filter((w) => (w.match(/[ً-ْٰۖ-ۭ]/g) ?? []).length < 2)
    .join(" ");
}

type Recognition = {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
const SpeechRec = (window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition })
  .SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: new () => Recognition }).webkitSpeechRecognition;

function Chat({ view, onBack }: { view: Matched; onBack: (() => void) | null }) {
  const t = useT();
  const { lang } = useLang();
  const { card } = view;
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // the model is chosen on the server; ?model=local|anthropic overrides it for the team's comparisons
  const provider = new URLSearchParams(window.location.search).get("model") ?? undefined;
  const [replyLang, setReplyLang] = useState("auto");
  const [open, setOpen] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState<number | null>(null);
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognition | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // braces: never return scrollIntoView(...) — recent Chrome returns a Promise, which React would call as cleanup
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
      rec.current?.stop();
    };
  }, []);

  const lastReply = [...msgs].reverse().find((m) => m.reply)?.reply;
  const activeLang = replyLang !== "auto" ? replyLang : lastReply?.language ?? lang;

  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    const history: Turn[] = msgs.map((m) => ({ role: m.role, content: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await ask(card, q, history, replyLang, provider);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, reply: r }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "assistant", text: `⚠ ${(err as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };

  const speak = (i: number, text: string, code: string) => {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    if (speaking === i) {
      setSpeaking(null);
      return;
    }
    const u = new SpeechSynthesisUtterance(speakable(text));
    u.lang = speechCode(code);
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(code));
    if (voice) u.voice = voice;
    u.onend = () => setSpeaking(null);
    u.onerror = () => setSpeaking(null);
    setSpeaking(i);
    synth.speak(u);
  };

  const listen = () => {
    if (!SpeechRec) return;
    if (listening) {
      rec.current?.stop();
      return;
    }
    const r = new SpeechRec();
    r.lang = speechCode(activeLang);
    r.interimResults = true;
    r.onresult = (e) => {
      const said = Array.from(e.results).map((res) => res[0]!.transcript).join(" ");
      setInput(said);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  };

  const name = lang === "ar" ? card.sura_name.ar : card.sura_name.en;
  return (
    <section className="sheet chat">
      <div className="chat-head">
        {onBack && (
          <button className="btn ghost back" onClick={onBack} aria-label={t("chat.back")}>
            {lang === "ar" ? "→" : "←"}
          </button>
        )}
        <img src={view.photo} alt="" className="chat-thumb" />
        <div className="chat-title">
          <b>{name} {card.ref.label} · {view.source === "read" ? t("chat.readShort") : t("chat.verifiedShort")}</b>
          <span>{t("chat.subtitle")}</span>
        </div>
        <img src="/mark.svg" alt="" className="chat-mark" />
      </div>
      <div className="chat-tools">
        <p className="banner" dir="auto">{lastReply?.banner ?? t("chat.banner")}</p>
        <div className="tool-row">
          <label className="lang-pick">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" /></svg>
            <select value={replyLang} onChange={(e) => setReplyLang(e.target.value)} aria-label={t("chat.lang")}>
              <option value="auto">
                {t("chat.auto")}{replyLang === "auto" && lastReply ? ` · ${lastReply.language_name}` : ""}
              </option>
              {CHAT_LANGS.map(([code, native]) => <option key={code} value={code}>{native}</option>)}
            </select>
          </label>
        </div>
      </div>
      <div className="msgs">
        {msgs.length === 0 && (
          <div className="suggest">
            <p className="any-lang">
              <span>{t("chat.anyLang")}</span>
              <span className="hello" dir="ltr">مرحبا · Hello · Bonjour · Merhaba · Salam · 你好 · Hola</span>
            </p>
            {(["chat.s1", "chat.s2", "chat.s3"] as const).map((k) => (
              <button key={k} className="bubble-btn" onClick={() => void send(t(k))}>{t(k)}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => {
          const referral = m.reply?.referral;
          const text = m.text.replace(/\s*\[D\d+\]/g, "").trim();
          const key = (c: Citation) => `${i}-${c.id}`;
          return (
            <div key={i} className={`bubble ${m.role} ${referral ? "referral" : ""}`}>
              {m.reply && (
                <div className="bubble-meta">
                  <span className="lang-tag">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" /></svg>
                    {m.reply.language_name}
                  </span>
                  {"speechSynthesis" in window && (
                    <button className={`speak ${speaking === i ? "on" : ""}`} onClick={() => speak(i, text, m.reply!.language)}
                      aria-label={t("chat.speak")} title={t("chat.speak")}>
                      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z" /><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11" /></svg>
                    </button>
                  )}
                </div>
              )}
              <p dir="auto">{text}</p>
              {referral && <p className="referral-line" dir="auto"><b>{t("chat.referral")}:</b> {referral}</p>}
              {m.reply && m.reply.citations.length > 0 && (
                <div className="cite-chips">
                  {m.reply.citations.map((c) => (
                    <button key={c.id} dir="auto" className={`cite-chip ${open === key(c) ? "on" : ""}`}
                      onClick={() => setOpen(open === key(c) ? null : key(c))}>
                      {citeLabel(c, card, t)}
                    </button>
                  ))}
                </div>
              )}
              {m.reply?.citations.filter((c) => open === key(c)).map((c) => (
                <div key={c.id} className="cite-body">
                  <p dir="auto" className={c.id === "D1" ? "quran small" : ""}>{c.text}</p>
                  <a href={c.url} target="_blank" rel="noopener noreferrer">{c.source}</a>
                </div>
              ))}
              {m.reply && <span className="gen-label">{t("chat.generated")}</span>}
            </div>
          );
        })}
        {busy && <ThinkingSteps />}
        <div ref={end} />
      </div>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
        {SpeechRec && (
          <button type="button" className={`mic ${listening ? "on" : ""}`} onClick={listen} aria-label={t("chat.mic")} title={t("chat.mic")}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </button>
        )}
        <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={listening ? t("chat.listening") : t("chat.placeholder")} maxLength={1000} />
        <button className="btn primary" disabled={busy || !input.trim()}>{t("chat.send")}</button>
      </form>
    </section>
  );
}
