import { describe, expect, it } from "vitest";
import { dictionaries, dirOf } from "./i18n";

describe("i18n", () => {
  it("has the same keys in every language, none empty", () => {
    const keys = Object.keys(dictionaries.ar).sort();
    for (const d of Object.values(dictionaries)) {
      expect(Object.keys(d).sort()).toEqual(keys);
      for (const v of Object.values(d)) expect(v.trim()).not.toBe("");
    }
  });
  it("Arabic is right-to-left", () => {
    expect(dirOf("ar")).toBe("rtl");
    expect(dirOf("en")).toBe("ltr");
  });
});
