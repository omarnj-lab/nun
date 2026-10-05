export type Ayah = { aya: number; text_uthmani: string; text_display: string; translation: string | null; audio: string };
export type Card = {
  ref: { sura: number; aya_from: number; aya_to: number; label: string };
  sura_name: { ar: string; en: string; en_meaning: string };
  juz: number;
  revelation: "meccan" | "medinan";
  ayahs: Ayah[];
  translation: { lang: string; translator: string; version: string; source: string } | null;
  recitation: { name: string; source: string; url: string };
  sources: { label: string; url: string }[];
};
export type ScanResult =
  | { status: "matched"; card: Card; panel: { id: string; inliers: number; coverage: number; polygon: number[][] | null; pairs: number[][] | null; reference: string | null } }
  | { status: "read"; card: Card; reading: Reading }
  | { status: "uncertain" | "not_quranic"; reason?: string; seen?: Seen };
/** What KhaṭṭVision saw (never its reading): script styles, theme, where the text is. */
export type Seen = { styles: string[]; theme: string | null; boxes: [number, number, number, number][] };
/** A verse found by the reading path: KhaṭṭVision read the panel and the reading matched this Quran passage. */
export type Reading = { score: number; letters: number; styles: string[]; theme: string | null; regions: Region[] };
export type Citation = { id: string; title: string; source: string; url: string; text: string };
export type ChatReply = {
  answer: string;
  citations: Citation[];
  level: "A" | "B" | "C" | "D";
  referral: string | null;
  banner: string;
  language: string; // ISO 639-1 code of the reply
  language_name: string; // its native name
  provider: string;
  model: string;
};
export type Region = { box: [number, number, number, number]; words: [number, number][] };
export type Regions = { available: false } | { available: true; styles: string[]; regions: Region[]; seconds: number };
export type Turn = { role: "user" | "assistant"; content: string };

async function check<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(String(detail));
  }
  return (await r.json()) as T;
}

export async function scan(file: Blob, lang: string): Promise<ScanResult> {
  const fd = new FormData();
  fd.append("image", file, "photo.jpg");
  fd.append("lang", lang);
  return check(await fetch("/api/scan", { method: "POST", body: fd }));
}

/** Text regions from KhaṭṭVision, aligned to the verse words (optional enrichment; may be unavailable). */
export async function regions(file: Blob, card: Card): Promise<Regions> {
  const fd = new FormData();
  fd.append("image", file, "photo.jpg");
  fd.append("sura", String(card.ref.sura));
  fd.append("aya_from", String(card.ref.aya_from));
  fd.append("aya_to", String(card.ref.aya_to));
  return check(await fetch("/api/regions", { method: "POST", body: fd }));
}

export async function ask(
  card: Card,
  message: string,
  history: Turn[],
  lang: string,
  provider?: string,
): Promise<ChatReply> {
  const body = {
    sura: card.ref.sura,
    aya_from: card.ref.aya_from,
    aya_to: card.ref.aya_to,
    message,
    history,
    lang,
    provider,
  };
  return check(
    await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  );
}

/** Downscale a camera photo before upload (phones send 12+ MP; the matcher works at 1024 px). */
export async function shrink(file: Blob, maxSide = 1280): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" } as ImageBitmapOptions);
    const s = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * s);
    canvas.height = Math.round(bmp.height * s);
    canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej()), "image/jpeg", 0.85));
  } catch {
    return file; // older browsers: send the original
  }
}

export type AyahRef = { sura: number; aya: number; label: string; text_display: string; translation: string | null; audio: string };
export type Stop = { id: string; sura: number; aya_from: number; aya_to: number; image: string; relation: "next" | "before" | "same_surah" };
export type Journey = { surah_ayahs: number; prev: AyahRef | null; next: AyahRef | null; stops: Stop[] };
export type SurahInfo = { sura: number; ar: string; en: string; ayahs: number; revelation: "meccan" | "medinan"; juz: number };
export type QuizOption = { text?: string; ar?: string; en?: string; key?: string; correct: boolean };
export type Quiz = { translator: string | null; questions: { id: "meaning" | "surah" | "revelation"; options: QuizOption[] }[] };

const getJson = async <T,>(url: string): Promise<T> => check<T>(await fetch(url));

export const journey = (card: Card, lang: string, panel?: string) =>
  getJson<Journey>(`/api/journey/${card.ref.sura}/${card.ref.aya_from}/${card.ref.aya_to}?lang=${lang}${panel ? `&panel=${encodeURIComponent(panel)}` : ""}`);
export const quranMap = () => getJson<SurahInfo[]>("/api/quran-map");
export const quiz = (card: Card) => getJson<Quiz>(`/api/quiz/${card.ref.sura}/${card.ref.aya_from}/${card.ref.aya_to}`);
export async function postQuiz(body: {
  panel?: string; sura: number; aya: number; lang: string; pre_correct: boolean | null; post_correct: number; post_total: number;
}): Promise<void> {
  await fetch("/api/quiz/result", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
