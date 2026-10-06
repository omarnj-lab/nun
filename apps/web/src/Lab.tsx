/* Nūn Lab: the team's open, fine-tuned calligraphy model as a product. Live "what our model sees" on any photo,
   the measured comparison with general vision models, how Nūn uses it, and the model card with open links.
   Benchmark numbers come from eval/results/2026-10-05 (195 real calligraphy panels; images internal, numbers public). */
import { useContext, useState } from "react";
import { shrink } from "./api";
import { I18nContext, arabicDigits, useT, type Key } from "./i18n";

type LabResult =
  | { available: false }
  | {
      available: true; styles: string[]; theme: string | null; boxes: [number, number, number, number][];
      nearest: { label: string; sura_ar: string; sura_en: string; score: number; letters: number } | null;
      reason: string; seconds: number;
    };

const HF_MODEL = "https://huggingface.co/Omartificial-Intelligence-Space/Nun-Vision-30B-Lora";
const CODE = "https://github.com/omarnj-lab/nun";

// eval/results/2026-10-05 (195 real panels, none in Nūn's collection): wrong verse shown = hallucination;
// precision = share of the verses a system shows that are right.
const BENCH: { key: string; halluc: number; precision: number; ours?: boolean }[] = [
  { key: "lab.sys.gpt", halluc: 35.4, precision: 62 },
  { key: "lab.sys.claude", halluc: 10.3, precision: 89 },
  { key: "lab.sys.nun", halluc: 1.0, precision: 96, ours: true },
];
const STYLE_ACC: [string, number][] = [["Naskh", 85], ["Thuluth", 86], ["Diwani", 36]];
const THEME_KEY: Record<string, Key> = {
  "names of Allah": "theme.names_allah", "devotional invocation": "theme.dua", hadith: "theme.hadith",
  "names of the Prophet": "theme.prophet", "names of companions": "theme.companions", dedication: "theme.dedication",
  "personal/place name": "theme.name", "non-religious": "theme.non_religious", quranic: "theme.quranic",
};
const STYLE_AR: Record<string, string> = {
  Thuluth: "الثلث", Diwani: "الديواني", Naskh: "النسخ", Kufic: "الكوفي", "Ruq'ah": "الرقعة", "Nasta'liq": "النستعليق",
};

export function Lab({ onBack }: { onBack: () => void }) {
  const t = useT();
  const { lang } = useContext(I18nContext);
  const num = (n: number | string) => (lang === "ar" ? arabicDigits(n) : String(n));
  const [photo, setPhoto] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<LabResult | null>(null);

  const run = async (file: Blob) => {
    setPhoto(URL.createObjectURL(file));
    setRes(null);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", await shrink(file), "photo.jpg");
      const r = await fetch("/api/lab/analyze", { method: "POST", body: fd });
      setRes(r.ok ? ((await r.json()) as LabResult) : { available: false });
    } catch {
      setRes({ available: false });
    } finally {
      setBusy(false);
    }
  };
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) void run(f);
  };
  const trySample = async (src: string) => void run(await (await fetch(src)).blob());

  return (
    <div className="lab">
      <button className="btn ghost lab-back" onClick={onBack}>{lang === "ar" ? "→" : "←"} {t("lab.back")}</button>

      <section className="lab-hero">
        <span className="track-pill">{t("lab.badge")}</span>
        <h1>Nūn Vision</h1>
        <p className="lab-sub">{t("lab.sub")}</p>
        <div className="lab-facts">
          <span><b>30B</b>{t("lab.f.base")}</span>
          <span><b>LoRA r16</b>{t("lab.f.lora")}</span>
          <span><b>{num("1,272")}</b>{t("lab.f.data")}</span>
          <span><b>4</b>{t("lab.f.tasks")}</span>
        </div>
        <div className="cta-row">
          <a className="cta primary" href={HF_MODEL} target="_blank" rel="noopener noreferrer">🤗 {t("lab.model")}</a>
          <a className="cta" href={CODE} target="_blank" rel="noopener noreferrer">{t("lab.code")}</a>
        </div>
      </section>

      <section className="lab-try">
        <h2>{t("lab.try")}</h2>
        <p className="muted">{t("lab.tryHint")}</p>
        <div className="lab-try-grid">
          <div className="lab-stage">
            {photo ? (
              <div className="photo-frame lab-frame">
                <img src={photo} alt="" />
                {res?.available && (
                  <svg viewBox="0 0 1 1" preserveAspectRatio="none">
                    {res.boxes.map((b, i) => (
                      <rect key={i} className="lab-box" style={{ animationDelay: `${i * 160}ms` }}
                        x={b[0]} y={b[1]} width={b[2] - b[0]} height={b[3] - b[1]} vectorEffect="non-scaling-stroke" />
                    ))}
                  </svg>
                )}
                {busy && <div className="scan-line" />}
              </div>
            ) : (
              <div className="lab-empty">{t("lab.empty")}</div>
            )}
            <div className="cta-row">
              <label className="cta primary">
                {t("hero.upload")}
                <input type="file" accept="image/*" hidden onChange={onPick} />
              </label>
              <button className="cta" onClick={() => void trySample("/panels/24_midnight_gold.jpg")}>{t("lab.sample")}</button>
            </div>
          </div>
          <div className="lab-out">
            {busy && <p className="lab-busy"><span className="spark" />{t("lab.busy")}</p>}
            {res && !res.available && <p className="muted">{t("lab.down")}</p>}
            {res?.available && (
              <dl className="lab-dl">
                <div><dt>{t("lab.out.style")}</dt><dd>{res.styles.map((s) => (lang === "ar" ? STYLE_AR[s] ?? s : s)).join("، ") || "—"}</dd></div>
                <div><dt>{t("lab.out.theme")}</dt><dd>{res.theme ? (THEME_KEY[res.theme] ? t(THEME_KEY[res.theme]!) : res.theme) : "—"}</dd></div>
                <div><dt>{t("lab.out.regions")}</dt><dd>{num(res.boxes.length)}</dd></div>
                <div>
                  <dt>{t("lab.out.nearest")}</dt>
                  <dd>
                    {res.nearest ? (
                      <>
                        {lang === "ar" ? res.nearest.sura_ar : res.nearest.sura_en} {res.nearest.label}
                        <small> · {t("lab.out.score").replace("{s}", num(Math.round(res.nearest.score))).replace("{n}", num(res.nearest.letters))}</small>
                        <span className="lab-unverified">{t("lab.unverified")}</span>
                      </>
                    ) : t("lab.out.none")}
                  </dd>
                </div>
                <div><dt>{t("lab.out.time")}</dt><dd>{num(res.seconds)} s · {t("lab.out.gpu")}</dd></div>
              </dl>
            )}
          </div>
        </div>
      </section>

      <section className="lab-bench">
        <h2>{t("lab.bench")}</h2>
        <p className="muted">{t("lab.benchSub")}</p>
        <h3>{t("lab.hallucTitle")}</h3>
        <div className="bench">
          {BENCH.map((b) => (
            <div key={b.key} className={`bench-row ${b.ours ? "ours" : ""}`}>
              <span className="bench-name">{t(b.key as Parameters<typeof t>[0])}</span>
              <div className="bench-bar" dir="ltr">
                <i className={b.ours ? "right" : "wrong"} style={{ width: `${Math.max(b.halluc * 2.5, 1.2)}%` }} />
              </div>
              <span className="bench-num"><b className={b.ours ? "" : "w"}>{num(b.halluc.toFixed(1))}٪</b> {t("lab.halluc")}</span>
            </div>
          ))}
        </div>
        <h3>{t("lab.precTitle")}</h3>
        <div className="bench">
          {BENCH.map((b) => (
            <div key={b.key} className={`bench-row ${b.ours ? "ours" : ""}`}>
              <span className="bench-name">{t(b.key as Parameters<typeof t>[0])}</span>
              <div className="bench-bar" dir="ltr"><i className="right" style={{ width: `${b.precision}%` }} /></div>
              <span className="bench-num"><b>{num(b.precision)}٪</b> {t("lab.prec")}</span>
            </div>
          ))}
        </div>
        <p className="lab-take">{t("lab.take")}</p>
        <h3>{t("lab.styleAcc")}</h3>
        <div className="style-acc">
          {STYLE_ACC.map(([s, v]) => (
            <div key={s}>
              <div className="ring" style={{ ["--v" as string]: `${v}%` }}><span>{num(v)}٪</span></div>
              <b>{lang === "ar" ? STYLE_AR[s] : s}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="lab-pipe">
        <h2>{t("lab.pipe")}</h2>
        <ol className="pipe">
          {(["p1", "p2", "p3", "p4", "p5"] as const).map((k, i) => (
            <li key={k} className={k === "p2" ? "ours" : ""}>
              <span className="pipe-n">{num(i + 1)}</span>
              <b>{t(`lab.${k}` as Parameters<typeof t>[0])}</b>
              <small>{t(`lab.${k}d` as Parameters<typeof t>[0])}</small>
            </li>
          ))}
        </ol>
      </section>

      <section className="lab-card">
        <h2>{t("lab.card")}</h2>
        <table>
          <tbody>
            {(["c1", "c2", "c3", "c4", "c5", "c6"] as const).map((k) => (
              <tr key={k}><th>{t(`lab.${k}` as Parameters<typeof t>[0])}</th><td>{t(`lab.${k}v` as Parameters<typeof t>[0])}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
