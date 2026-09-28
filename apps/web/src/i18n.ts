import { createContext, useContext } from "react";

// UI strings only. Religious content (verses, translations, tafsir) never lives here: it comes from the API.
const ar = {
  "app.name": "نون",
  "app.tagline": "صوّر الخط العربي، وتعرّف على ما كُتب",
  "lang.switch": "English",
  "home.capture": "التقط صورة",
  "home.upload": "اختر من المعرض",
  "home.selected": "الصورة المختارة",
  "home.notReady": "التعرّف على الصورة قيد الإنشاء في هذه النسخة.",
  "home.privacy": "لا نحفظ صورك؛ تُعالج ثم تُحذف.",
  "footer.ai": "نون مساعد يعمل بالذكاء الاصطناعي ويعتمد على مصادر معتمدة.",
} as const;

export type Key = keyof typeof ar;

const en: Record<Key, string> = {
  "app.name": "Nūn",
  "app.tagline": "Photograph Arabic calligraphy and learn what it says",
  "lang.switch": "العربية",
  "home.capture": "Take a photo",
  "home.upload": "Choose from gallery",
  "home.selected": "Selected photo",
  "home.notReady": "Recognition is still being built in this version.",
  "home.privacy": "Your photos are not stored; they are processed and discarded.",
  "footer.ai": "Nūn is an AI-assisted guide built on approved sources.",
};

export const dictionaries = { ar, en } as const;
export type Lang = keyof typeof dictionaries;
export const dirOf = (lang: Lang): "rtl" | "ltr" => (lang === "ar" ? "rtl" : "ltr");

export const I18nContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: "ar",
  setLang: () => {},
});

export function useT() {
  const { lang } = useContext(I18nContext);
  return (key: Key): string => dictionaries[lang][key];
}
