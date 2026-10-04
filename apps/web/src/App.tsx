import { useContext, useEffect, useRef, useState } from "react";
import { ask, scan, shrink, type Card, type ChatReply, type Citation, type Turn } from "./api";
import { I18nContext, arabicDigits, dirOf, useT, type Key, type Lang } from "./i18n";

type Matched = { photo: string; card: Card; polygon: number[][] | null };
type View =
  | { name: "home" }
  | { name: "scanning"; photo: string }
  | ({ name: "result"; chat: boolean } & Matched)
  | { name: "uncertain"; photo: string }
  | { name: "error"; message: string };

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
    <div className={`app ${view.name === "result" || view.name === "home" ? "wide" : ""} view-${view.name}`}>
      <Header onHome={home} />
      <main className="main">
        {view.name === "home" && <Home onView={setView} />}
        {view.name === "scanning" && <Scanning photo={view.photo} />}
        {view.name === "result" && (
          <Workspace view={view} setChat={(chat) => setView({ ...view, chat })} onAgain={home} />
        )}
        {view.name === "uncertain" && <Uncertain photo={view.photo} onAgain={home} />}
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

function Header({ onHome }: { onHome: () => void }) {
  const t = useT();
  const { lang, setLang } = useLang();
  return (
    <header className="header">
      <button className="logo-btn" onClick={onHome} aria-label={t("app.name")}>
        <img src="/logo.svg" alt={t("app.name")} className="logo" />
      </button>
      <button className="btn ghost" onClick={() => setLang(lang === "ar" ? "en" : "ar")}>{t("lang.switch")}</button>
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
  const run = async (file: Blob) => {
    const photo = URL.createObjectURL(file); // stays in the browser; only a downscaled copy is sent
    onView({ name: "scanning", photo });
    try {
      const r = await scan(await shrink(file), lang);
      onView(
        r.status === "matched"
          ? { name: "result", chat: false, photo, card: r.card, polygon: r.panel.polygon ?? null }
          : { name: "uncertain", photo },
      );
    } catch (err) {
      onView({ name: "error", message: (err as Error).message });
    }
  };
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) void run(file);
  };
  const trySample = async () => {
    const blob = await (await fetch("/sample.jpg")).blob();
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
          <button className="sample-link" onClick={() => void trySample()}>
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
        <div className="marquee" dir="ltr">
          <div className="marquee-track">
            {[...PANELS, ...PANELS].map((id, i) => (
              <img key={i} src={panelSrc(id)} alt="" loading="lazy" />
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
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, 2)), 900);
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
        {(["scan.step1", "scan.step2", "scan.step3"] as const).map((k, i) => (
          <li key={k} className={i < step ? "done" : i === step ? "now" : ""}>
            <span className="dot">{i < step ? "✓" : ""}</span>{t(k)}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Uncertain({ photo, onAgain }: { photo: string; onAgain: () => void }) {
  const t = useT();
  return (
    <section className="sheet narrow">
      <img src={photo} alt="" className="photo" />
      <div className="notice warn">
        <span className="badge warn">{t("uncertain.badge")}</span>
        <h2>{t("uncertain.title")}</h2>
        <p>{t("uncertain.body")}</p>
        <p className="muted">{t("uncertain.tips")}</p>
        <p className="muted">{t("uncertain.guide")}</p>
      </div>
      <button className="btn primary" onClick={onAgain}>{t("scan.again")}</button>
    </section>
  );
}

const WIDE = "(min-width: 960px)";

/** Desktop: verse info and chat side by side (info on the reading-start side). Phone: info, then chat. */
function Workspace({ view, setChat, onAgain }: {
  view: Matched & { chat: boolean };
  setChat: (c: boolean) => void;
  onAgain: () => void;
}) {
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
        <Info view={view} onAsk={null} onAgain={onAgain} />
        <Chat view={view} onBack={null} />
      </div>
    );
  }
  return view.chat ? (
    <Chat view={view} onBack={() => setChat(false)} />
  ) : (
    <Info view={view} onAsk={() => setChat(true)} onAgain={onAgain} />
  );
}

/** The visitor's photo with the matched panel's boundary (projected by the matcher's homography) drawn in gold. */
function PhotoWithOutline({ photo, polygon }: { photo: string; polygon: number[][] | null }) {
  return (
    <figure className="photo-box">
      <div className="photo-frame">
        <img src={photo} alt="" />
        {polygon && (
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
            <polygon points={polygon.map((p) => p.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />
          </svg>
        )}
      </div>
    </figure>
  );
}

function Info({ view, onAsk, onAgain }: { view: Matched; onAsk: (() => void) | null; onAgain: () => void }) {
  const t = useT();
  const { lang } = useLang();
  const { card } = view;
  const num = (n: number) => (lang === "ar" ? arabicDigits(n) : String(n));
  const ref = card.ref;
  const ayahs = ref.aya_to !== ref.aya_from ? `${num(ref.aya_from)}–${num(ref.aya_to)}` : num(ref.aya_from);
  return (
    <section className="sheet info">
      <PhotoWithOutline photo={view.photo} polygon={view.polygon} />
      <p className="caption">{t("card.flow")}</p>
      <div className="chips">
        <span className="chip ok">✓ {t("card.verified")}</span>
        <span className="chip">{t("card.quranic")}</span>
      </div>
      <div className="quran" dir="rtl" lang="ar">
        {card.ayahs.map((a) => (
          <span key={a.aya}>
            {a.text_display} <span className="aya-no">﴿{arabicDigits(a.aya)}﴾</span>{" "}
          </span>
        ))}
      </div>
      {card.translation && (
        <blockquote className="translation" dir="ltr" lang="en">
          {card.ayahs.map((a) => (
            <p key={a.aya}>“{(a.translation ?? "").replace(/\[\d+\]/g, "").trim()}”</p>
          ))}
          <cite>{card.translation.translator} · v{card.translation.version} · {card.translation.source}</cite>
        </blockquote>
      )}
      <div className="tiles">
        <Tile label={t("card.surahName")} value={lang === "ar" ? card.sura_name.ar : card.sura_name.en} />
        <Tile label={t("card.ayahNo")} value={`${num(ref.sura)} : ${ayahs}`} />
        <Tile label={t("card.juz")} value={num(card.juz)} />
        <Tile label={t("card.revelation")} value={card.revelation === "meccan" ? t("card.meccan") : t("card.medinan")} />
        <Listen card={card} />
      </div>
      {onAsk && <button className="btn primary big" onClick={onAsk}>{t("card.ask")}</button>}
      <p className="sources-line">{t("card.sourcesLine")} · {card.recitation.name} ({card.recitation.source})</p>
      <button className="btn soft" onClick={onAgain}>{t("scan.again")}</button>
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

/** Plays the card's ayahs one after another (human recitation from EveryAyah). */
function Listen({ card }: { card: Card }) {
  const t = useT();
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    return () => {
      audio.current?.pause();
    };
  }, []);
  const toggle = () => {
    if (playing) {
      audio.current?.pause();
      setPlaying(false);
      return;
    }
    let i = 0;
    const play = () => {
      const a = new Audio(card.ayahs[i]!.audio);
      audio.current = a;
      a.onended = () => {
        i += 1;
        if (i < card.ayahs.length) play();
        else setPlaying(false);
      };
      void a.play().catch(() => setPlaying(false));
    };
    play();
    setPlaying(true);
  };
  return (
    <button className="tile listen" onClick={toggle}>
      <span className="tile-label">{t("card.recitation")}</span>
      <span className="tile-value">{playing ? `■ ${t("card.stop")}` : `▶ ${t("card.listen")}`}</span>
    </button>
  );
}

type Msg = { role: "user" | "assistant"; text: string; reply?: ChatReply };

function citeLabel(c: Citation, card: Card, t: ReturnType<typeof useT>): string {
  if (c.id === "D1") return t("cite.quran");
  if (/translation/i.test(c.title)) return card.translation?.translator.replace("International", "Intl.") ?? c.source;
  return t("cite.facts");
}

function Chat({ view, onBack }: { view: Matched; onBack: (() => void) | null }) {
  const t = useT();
  const { lang } = useLang();
  const { card } = view;
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState<"local" | "anthropic">("local");
  const [open, setOpen] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // braces: never return scrollIntoView(...) — recent Chrome returns a Promise, which React would call as cleanup
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);

  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    const history: Turn[] = msgs.map((m) => ({ role: m.role, content: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await ask(card, q, history, lang, provider);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, reply: r }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "assistant", text: `⚠ ${(err as Error).message}` }]);
    } finally {
      setBusy(false);
    }
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
          <b>{name} {card.ref.label} · {t("chat.verifiedShort")}</b>
          <span>{t("chat.subtitle")}</span>
        </div>
        <img src="/mark.svg" alt="" className="chat-mark" />
      </div>
      <div className="chat-tools">
        <p className="banner">{t("chat.banner")}</p>
        <div className="seg" role="group" aria-label={t("chat.model")}>
          <button className={provider === "local" ? "on" : ""} onClick={() => setProvider("local")}>{t("chat.local")}</button>
          <button className={provider === "anthropic" ? "on" : ""} onClick={() => setProvider("anthropic")}>{t("chat.claude")}</button>
        </div>
      </div>
      <div className="msgs">
        {msgs.length === 0 && (
          <div className="suggest">
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
              <p dir="auto">{text}</p>
              {referral && <p className="referral-line" dir="auto"><b>{t("chat.referral")}:</b> {referral}</p>}
              {m.reply && m.reply.citations.length > 0 && (
                <div className="cite-chips">
                  {m.reply.citations.map((c) => (
                    <button key={c.id} className={`cite-chip ${open === key(c) ? "on" : ""}`}
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
        {busy && <div className="bubble assistant typing"><span /><span /><span /></div>}
        <div ref={end} />
      </div>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
        <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("chat.placeholder")} maxLength={1000} />
        <button className="btn primary" disabled={busy || !input.trim()}>{t("chat.send")}</button>
      </form>
    </section>
  );
}
