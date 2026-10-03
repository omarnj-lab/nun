export type Ayah = { aya: number; text_uthmani: string; translation: string | null; audio: string };
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
  | { status: "matched"; card: Card; panel: { id: string; inliers: number; coverage: number } }
  | { status: "uncertain" };
export type Citation = { id: string; title: string; source: string; url: string; text: string };
export type ChatReply = {
  answer: string;
  citations: Citation[];
  level: "A" | "B" | "C" | "D";
  referral: string | null;
  banner: string;
  provider: string;
  model: string;
};
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

export async function ask(
  card: Card,
  message: string,
  history: Turn[],
  lang: string,
  provider: string,
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

/** Downscale a camera photo before upload (phones send 12+ MP; the matcher needs ~1600 px). */
export async function shrink(file: File, maxSide = 1600): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" } as ImageBitmapOptions);
    const s = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * s);
    canvas.height = Math.round(bmp.height * s);
    canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej()), "image/jpeg", 0.9));
  } catch {
    return file; // older browsers: send the original
  }
}
