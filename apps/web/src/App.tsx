import { useContext, useEffect, useRef, useState } from "react";
import { ask, scan, shrink, type Card, type ChatReply, type Citation, type Turn } from "./api";
import { I18nContext, arabicDigits, dirOf, useT, type Lang } from "./i18n";

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
    <div className={`app ${view.name === "result" ? "wide" : ""}`}>
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

function Home({ onView }: { onView: (v: View) => void }) {
  const t = useT();
  const { lang } = useLang();
  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
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
  return (
    <section className="home">
      <h1 className="hero">{t("home.title")}</h1>
      <div className="viewfinder">
        <img src="/sample.jpg" alt="" />
        <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
      </div>
      <label className="shutter" aria-label={t("home.capture")}>
        <span className="shutter-ring"><span className="shutter-dot" /></span>
        <span>{t("home.shutter")}</span>
        <input type="file" accept="image/*" capture="environment" hidden onChange={onPick} />
      </label>
      <label className="btn soft">
        {t("home.upload")}
        <input type="file" accept="image/*" hidden onChange={onPick} />
      </label>
      <p className="hint">{t("home.hint")}</p>
      <p className="hint">{t("home.privacy")}</p>
    </section>
  );
}

function Scanning({ photo }: { photo: string }) {
  const t = useT();
  return (
    <section className="home">
      <div className="viewfinder live">
        <span className="pill">{t("scan.pill")}</span>
        <img src={photo} alt="" />
        <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
        <div className="scan-line" />
      </div>
      <p className="hint">{t("scan.working")}</p>
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
