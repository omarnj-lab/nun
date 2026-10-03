import { useContext, useEffect, useRef, useState } from "react";
import { ask, scan, shrink, type Card, type ChatReply, type Turn } from "./api";
import { I18nContext, arabicDigits, dirOf, useT, type Lang } from "./i18n";

type View =
  | { name: "home" }
  | { name: "scanning"; photo: string }
  | { name: "card"; photo: string; card: Card }
  | { name: "uncertain"; photo: string }
  | { name: "error"; message: string }
  | { name: "chat"; photo: string; card: Card };

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("nun-lang");
    if (saved === "ar" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  return "ar";
}

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
  return (
    <>
      <Header onHome={() => setView({ name: "home" })} />
      <main className="container">
        {view.name === "home" && <Home onScanned={setView} />}
        {view.name === "scanning" && <Scanning photo={view.photo} />}
        {view.name === "card" && (
          <CardView photo={view.photo} card={view.card} onAsk={() => setView({ ...view, name: "chat" })}
            onAgain={() => setView({ name: "home" })} />
        )}
        {view.name === "uncertain" && <Uncertain photo={view.photo} onAgain={() => setView({ name: "home" })} />}
        {view.name === "error" && (
          <section className="panel">
            <h2>{t("error.title")}</h2>
            <p>{view.message}</p>
            <button className="btn primary" onClick={() => setView({ name: "home" })}>{t("scan.again")}</button>
          </section>
        )}
        {view.name === "chat" && <Chat card={view.card} onBack={() => setView({ ...view, name: "card" })} />}
      </main>
      <footer className="container footer">{t("footer.ai")}</footer>
    </>
  );
}

function Header({ onHome }: { onHome: () => void }) {
  const t = useT();
  return (
    <header className="header">
      <div className="container header-row">
        <button className="logo-btn" onClick={onHome} aria-label={t("app.name")}>
          <img src="/logo.svg" alt={t("app.name")} className="logo" />
        </button>
        <I18nContext.Consumer>
          {({ lang, setLang }) => (
            <button className="btn ghost" onClick={() => setLang(lang === "ar" ? "en" : "ar")}>{t("lang.switch")}</button>
          )}
        </I18nContext.Consumer>
      </div>
    </header>
  );
}

function Home({ onScanned }: { onScanned: (v: View) => void }) {
  const t = useT();
  const { lang } = useContextLang();
  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const photo = URL.createObjectURL(file); // stays in the browser
    onScanned({ name: "scanning", photo });
    try {
      const r = await scan(await shrink(file), lang);
      onScanned(r.status === "matched" ? { name: "card", photo, card: r.card } : { name: "uncertain", photo });
    } catch (err) {
      onScanned({ name: "error", message: (err as Error).message });
    }
  };
  return (
    <section className="home">
      <h1 className="title">{t("app.name")}</h1>
      <p className="tagline">{t("app.tagline")}</p>
      <div className="actions">
        <label className="btn primary big">
          {t("home.capture")}
          <input type="file" accept="image/*" capture="environment" hidden onChange={onPick} />
        </label>
        <label className="btn">
          {t("home.upload")}
          <input type="file" accept="image/*" hidden onChange={onPick} />
        </label>
      </div>
      <p className="hint">{t("home.hint")}</p>
      <p className="privacy">{t("home.privacy")}</p>
    </section>
  );
}

function Scanning({ photo }: { photo: string }) {
  const t = useT();
  return (
    <section className="panel center">
      <div className="scan-frame">
        <img src={photo} alt="" />
        <div className="scan-line" />
      </div>
      <p className="muted">{t("scan.working")}</p>
    </section>
  );
}

function Uncertain({ photo, onAgain }: { photo: string; onAgain: () => void }) {
  const t = useT();
  return (
    <section className="panel">
      <img src={photo} alt="" className="thumb" />
      <h2 className="warn-title">{t("uncertain.title")}</h2>
      <p>{t("uncertain.body")}</p>
      <p className="muted">{t("uncertain.tips")}</p>
      <p className="muted">{t("uncertain.guide")}</p>
      <button className="btn primary" onClick={onAgain}>{t("scan.again")}</button>
    </section>
  );
}

function Chips({ card }: { card: Card }) {
  const t = useT();
  const { lang } = useContextLang();
  const num = (n: number) => (lang === "ar" ? arabicDigits(n) : String(n));
  const ayahs = card.ref.aya_to !== card.ref.aya_from ? `${num(card.ref.aya_from)}–${num(card.ref.aya_to)}` : num(card.ref.aya_from);
  return (
    <div className="chips">
      <span className="chip">{t("card.surah")} {lang === "ar" ? card.sura_name.ar : card.sura_name.en} · {num(card.ref.sura)}</span>
      <span className="chip">{t("card.ayah")} {ayahs}</span>
      <span className="chip">{t("card.juz")} {num(card.juz)}</span>
      <span className="chip">{card.revelation === "meccan" ? t("card.meccan") : t("card.medinan")}</span>
    </div>
  );
}

function useContextLang() {
  return useContext(I18nContext);
}

function CardView({ photo, card, onAsk, onAgain }: { photo: string; card: Card; onAsk: () => void; onAgain: () => void }) {
  const t = useT();
  return (
    <section className="panel">
      <div className="card-head">
        <img src={photo} alt="" className="thumb small" />
        <span className="ok-chip">✓ {t("card.matched")}</span>
      </div>
      <Chips card={card} />
      <div className="quran" dir="rtl" lang="ar">
        {card.ayahs.map((a) => (
          <span key={a.aya}>
            {a.text_uthmani} <span className="aya-no">﴿{arabicDigits(a.aya)}﴾</span>{" "}
          </span>
        ))}
      </div>
      {card.translation && (
        <div className="translation" dir="ltr" lang="en">
          <h3>{t("card.translation")}</h3>
          {card.ayahs.map((a) => (
            <p key={a.aya}>({a.aya}) {a.translation}</p>
          ))}
          <p className="muted small-text">
            {card.translation.translator} · v{card.translation.version} · {card.translation.source}
          </p>
        </div>
      )}
      <div className="recitation">
        <h3>{t("card.recitation")}</h3>
        {card.ayahs.map((a) => (
          <audio key={a.aya} controls preload="none" src={a.audio} />
        ))}
        <p className="muted small-text">{card.recitation.name} · {card.recitation.source}</p>
      </div>
      <button className="btn primary big" onClick={onAsk}>{t("card.ask")}</button>
      <details className="sources">
        <summary>{t("card.sources")}</summary>
        <ul>
          {card.sources.map((s) => (
            <li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a></li>
          ))}
        </ul>
      </details>
      <button className="btn" onClick={onAgain}>{t("scan.again")}</button>
    </section>
  );
}

type Msg = { role: "user" | "assistant"; text: string; reply?: ChatReply };

function Chat({ card, onBack }: { card: Card; onBack: () => void }) {
  const t = useT();
  const { lang } = useContextLang();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [provider, setProvider] = useState<"local" | "anthropic">("local");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs, busy]);

  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    const history: Turn[] = msgs.map((m) => ({ role: m.role, content: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await ask(card, q, history, lang, provider);
      setBanner(r.banner);
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, reply: r }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "assistant", text: `⚠ ${(err as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel chat">
      <div className="chat-top">
        <button className="btn ghost" onClick={onBack}>← {t("chat.back")}</button>
        <div className="seg" role="group" aria-label={t("chat.model")}>
          <button className={provider === "local" ? "on" : ""} onClick={() => setProvider("local")}>{t("chat.local")}</button>
          <button className={provider === "anthropic" ? "on" : ""} onClick={() => setProvider("anthropic")}>{t("chat.claude")}</button>
        </div>
      </div>
      <h2>{t("chat.title")} · {lang === "ar" ? card.sura_name.ar : card.sura_name.en} {card.ref.label}</h2>
      <p className="banner">{banner ?? (lang === "ar" ? "أنا مساعد ذكي يجيب من مصادر معتمدة، ولست عالمًا أو مفتيًا." : "I am an AI assistant that answers from approved sources. I am not a scholar or a mufti.")}</p>
      {msgs.length === 0 && (
        <div className="suggest">
          {(["chat.s1", "chat.s2", "chat.s3"] as const).map((k) => (
            <button key={k} className="btn" onClick={() => send(t(k))}>{t(k)}</button>
          ))}
        </div>
      )}
      <div className="msgs">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant" && m.reply && <span className="gen-label">{t("chat.generated")}</span>}
            <p dir="auto">{m.text}</p>
            {m.reply && m.reply.citations.length > 0 && (
              <details className="cites">
                <summary>{t("chat.sources")}: {m.reply.citations.map((c) => c.id).join(", ")}</summary>
                {m.reply.citations.map((c) => (
                  <div key={c.id} className="cite">
                    <b>[{c.id}] {c.title}</b>
                    <p dir="auto" className={c.id === "D1" ? "quran small-q" : ""}>{c.text}</p>
                    <a href={c.url} target="_blank" rel="noopener noreferrer">{c.source}</a>
                  </div>
                ))}
              </details>
            )}
            {m.reply?.referral && (
              <div className="referral"><b>{t("chat.referral")}:</b> {m.reply.referral}</div>
            )}
          </div>
        ))}
        {busy && <div className="msg assistant muted">{t("chat.thinking")}</div>}
        <div ref={end} />
      </div>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
        <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("chat.placeholder")} maxLength={1000} />
        <button className="btn primary" disabled={busy || !input.trim()}>{t("chat.send")}</button>
      </form>
    </section>
  );
}
