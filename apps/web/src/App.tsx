import { useEffect, useState } from "react";
import { I18nContext, dirOf, useT, type Lang } from "./i18n";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("nun-lang");
    if (saved === "ar" || saved === "en") return saved;
  } catch {
    /* storage unavailable: fall back to Arabic */
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
  return (
    <>
      <Header />
      <main className="container">
        <Home />
      </main>
      <footer className="container footer">{t("footer.ai")}</footer>
    </>
  );
}

function Header() {
  const t = useT();
  return (
    <header className="header">
      <div className="container header-row">
        <img src="/logo.svg" alt={t("app.name")} className="logo" />
        <LangSwitch label={t("lang.switch")} />
      </div>
    </header>
  );
}

function LangSwitch({ label }: { label: string }) {
  return (
    <I18nContext.Consumer>
      {({ lang, setLang }) => (
        <button className="btn ghost" onClick={() => setLang(lang === "ar" ? "en" : "ar")}>
          {label}
        </button>
      )}
    </I18nContext.Consumer>
  );
}

function Home() {
  const t = useT();
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setPreview(URL.createObjectURL(f)); // stays in the browser; nothing is uploaded in this version
  };
  return (
    <section className="home">
      <h1 className="title">{t("app.name")}</h1>
      <p className="tagline">{t("app.tagline")}</p>
      <div className="actions">
        <label className="btn primary">
          {t("home.capture")}
          <input type="file" accept="image/*" capture="environment" hidden onChange={onPick} />
        </label>
        <label className="btn">
          {t("home.upload")}
          <input type="file" accept="image/*" hidden onChange={onPick} />
        </label>
      </div>
      {preview && (
        <figure className="preview">
          <img src={preview} alt={t("home.selected")} />
          <figcaption>{t("home.notReady")}</figcaption>
        </figure>
      )}
      <p className="privacy">{t("home.privacy")}</p>
    </section>
  );
}
