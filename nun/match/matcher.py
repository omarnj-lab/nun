"""Photo → panel matching (PLAN_NOW step 1): is this photo one of the panels in our collection, and which?

Two stages, standard for flat artwork:
  1. shortlist: DINOv2-small global embedding (cosine) → top-k collection photos;
  2. verify: RootSIFT keypoints + ratio test + RANSAC homography against each shortlisted photo; the number of
     geometrically consistent matches (inliers) decides. Below the threshold the answer is "no match" (never guess).
A physical panel may have several collection photos (panel_group); the best-verified photo wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

EMBED_MODEL = "facebook/dinov2-small"
SIFT_SIDE = 1024  # long side used for keypoints
MIN_INLIERS_DEFAULT = 20  # chosen by scripts/match_test.py (2026-10-02)
MIN_COVERAGE_DEFAULT = 0.4


def _gray(img: Image.Image, side: int = SIFT_SIDE) -> np.ndarray:
    im = img.convert("RGB")
    im.thumbnail((side, side), Image.Resampling.LANCZOS)
    g = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2GRAY)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)  # evens out glare / low light


def _root_sift(desc: np.ndarray | None) -> np.ndarray | None:
    if desc is None or len(desc) == 0:
        return None
    desc = desc / (np.abs(desc).sum(axis=1, keepdims=True) + 1e-7)
    return np.sqrt(desc).astype(np.float32)


@dataclass
class Entry:
    id: str
    group: str
    emb: np.ndarray
    kps: np.ndarray  # (n, 2) keypoint coordinates
    desc: np.ndarray | None
    shape: tuple[int, int]
    text_box: tuple[float, float, float, float] = (0.2, 0.2, 0.8, 0.8)  # x0, y0, x1, y1 as fractions of the photo


@dataclass
class Match:
    id: str | None
    group: str | None
    inliers: int
    cosine: float
    accepted: bool
    coverage: float = 0.0  # share of the panel's central cells holding inliers (see _verify)
    candidates: list[tuple[str, int, float, float]] = field(default_factory=list)  # (id, inliers, cosine, coverage)
    polygon: list[list[float]] | None = None  # the matched panel's corners in the visitor's photo (fractions x, y)
    pairs: list[list[float]] | None = None  # sample of verified point pairs [qx, qy, rx, ry] (fractions), for the UI


class PanelMatcher:
    def __init__(
        self,
        device: str = "cuda",
        min_inliers: int = MIN_INLIERS_DEFAULT,
        min_coverage: float = MIN_COVERAGE_DEFAULT,
        shortlist: int = 10,
    ) -> None:
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self.torch = torch
        self.device = device if torch.cuda.is_available() else "cpu"
        self.proc = AutoImageProcessor.from_pretrained(EMBED_MODEL)
        self.model = AutoModel.from_pretrained(EMBED_MODEL).to(self.device).eval()
        self.sift = cv2.SIFT_create(nfeatures=4000)
        self.matcher = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 5}, {"checks": 64})
        self.min_inliers = min_inliers
        self.min_coverage = min_coverage
        self.shortlist = shortlist
        self.entries: list[Entry] = []

    def embed(self, images: list[Image.Image]) -> np.ndarray:
        with self.torch.inference_mode():
            inputs = self.proc(images=[im.convert("RGB") for im in images], return_tensors="pt").to(self.device)
            out = self.model(**inputs).last_hidden_state
            v = self.torch.cat([out[:, 0], out[:, 1:].mean(1)], dim=1)  # CLS + mean patch token
            v = self.torch.nn.functional.normalize(v, dim=1)
        return v.float().cpu().numpy()

    def features(self, img: Image.Image) -> tuple[np.ndarray, np.ndarray | None, tuple[int, int]]:
        g = _gray(img)
        kps, desc = self.sift.detectAndCompute(g, None)
        pts = np.array([k.pt for k in kps], dtype=np.float32).reshape(-1, 2)
        return pts, _root_sift(desc), g.shape

    def add(
        self,
        id: str,
        img: Image.Image,
        group: str | None = None,
        emb: np.ndarray | None = None,
        text_box: tuple[float, float, float, float] | None = None,
    ) -> None:
        """text_box: where the text is on this collection photo (fractions x0, y0, x1, y1); the coverage check then
        counts inliers inside it instead of the middle 60%."""
        pts, desc, shape = self.features(img)
        e = self.embed([img])[0] if emb is None else emb
        entry = Entry(id, group or id, e, pts, desc, shape)
        if text_box:
            entry.text_box = tuple(float(v) for v in text_box)
        self.entries.append(entry)

    def add_many(self, items: list[tuple], batch: int = 32) -> None:
        """items: (id, image, group) or (id, image, group, text_box)."""
        for i in range(0, len(items), batch):
            chunk = items[i : i + batch]
            embs = self.embed([it[1] for it in chunk])
            for it, e in zip(chunk, embs, strict=True):
                self.add(it[0], it[1], it[2], emb=e, text_box=it[3] if len(it) > 3 else None)

    def _verify(self, q_pts, q_desc, e: Entry) -> tuple[int, float]:
        inl, cov, _ = self._verify_h(q_pts, q_desc, e)
        return inl, cov

    def _verify_h(self, q_pts, q_desc, e: Entry) -> tuple[int, float, np.ndarray | None]:
        """→ (RANSAC inliers, text coverage). Coverage = share of the 4×4 cells over the text box (default: the middle
        60%) of the collection photo that hold ≥ 2 inliers. Panels that share a frame, border or tile pattern but carry
        different text match only around the edge (low coverage); the same panel also matches across its text (high)."""
        if q_desc is None or e.desc is None or len(q_desc) < 8 or len(e.desc) < 8:
            return 0, 0.0, None
        knn = self.matcher.knnMatch(q_desc, e.desc, k=2)
        good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < 8:
            return 0, 0.0, None
        src = q_pts[[m.queryIdx for m in good]]
        dst = e.kps[[m.trainIdx for m in good]]
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        if H is None or mask is None:
            return 0, 0.0, None
        # reject degenerate homographies (collapsed or mirrored projections are not a photo of a flat panel)
        det = np.linalg.det(H[:2, :2])
        if not (0.02 < abs(det) < 50) or det < 0:
            return 0, 0.0, None
        pts = dst[mask.ravel().astype(bool)]
        h, w = e.shape
        x0, y0, x1, y1 = e.text_box
        u = (pts[:, 0] / w - x0) / max(x1 - x0, 1e-6)
        v = (pts[:, 1] / h - y0) / max(y1 - y0, 1e-6)
        inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        cells = np.zeros((4, 4), int)
        np.add.at(cells, ((v[inside] * 4).astype(int), (u[inside] * 4).astype(int)), 1)
        return int(mask.sum()), float((cells >= 2).mean()), H

    @staticmethod
    def _outline(H, e: Entry, q_shape) -> list[list[float]] | None:
        """Project the collection photo's corners into the visitor's photo: the panel's boundary for the UI."""
        if H is None:
            return None
        try:
            Hi = np.linalg.inv(H)
        except np.linalg.LinAlgError:
            return None
        h, w = e.shape
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        q = cv2.perspectiveTransform(corners, Hi).reshape(-1, 2)
        qh, qw = q_shape
        return [[round(float(x / qw), 4), round(float(y / qh), 4)] for x, y in q]

    def _pairs(self, q_pts, q_desc, e: Entry, q_shape, n: int = 48) -> list[list[float]] | None:
        """A spread-out sample of RANSAC-verified matches between the visitor's photo and the collection photo."""
        if q_desc is None or e.desc is None or len(q_desc) < 8 or len(e.desc) < 8:
            return None
        knn = self.matcher.knnMatch(q_desc, e.desc, k=2)
        good = [m for m, nn in (p for p in knn if len(p) == 2) if m.distance < 0.75 * nn.distance]
        if len(good) < 8:
            return None
        src = q_pts[[m.queryIdx for m in good]]
        dst = e.kps[[m.trainIdx for m in good]]
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        if mask is None:
            return None
        keep = np.flatnonzero(mask.ravel())
        if len(keep) > n:
            keep = keep[np.linspace(0, len(keep) - 1, n).astype(int)]
        qh, qw = q_shape
        h, w = e.shape
        return [
            [
                round(float(src[i, 0] / qw), 4),
                round(float(src[i, 1] / qh), 4),
                round(float(dst[i, 0] / w), 4),
                round(float(dst[i, 1] / h), 4),
            ]
            for i in keep
        ]

    def match(self, img: Image.Image, emb: np.ndarray | None = None) -> Match:
        if not self.entries:
            return Match(None, None, 0, 0.0, False)
        q = self.embed([img])[0] if emb is None else emb
        sims = np.stack([e.emb for e in self.entries]) @ q
        order = np.argsort(-sims)[: self.shortlist]
        q_pts, q_desc, q_shape = self.features(img)
        cands, homs = [], {}
        for i in order:
            inl, cov, H = self._verify_h(q_pts, q_desc, self.entries[i])
            cands.append((self.entries[i], inl, float(sims[i]), cov))
            homs[self.entries[i].id] = H
        cands.sort(key=lambda c: (c[1] * (0.25 + c[3]), c[2]), reverse=True)  # favour agreement across the text
        best, inl, cos, cov = cands[0]
        accepted = inl >= self.min_inliers and cov >= self.min_coverage
        return Match(
            pairs=self._pairs(q_pts, q_desc, best, q_shape) if accepted else None,
            polygon=self._outline(homs.get(best.id), best, q_shape),
            id=best.id,
            group=best.group,
            inliers=inl,
            cosine=cos,
            accepted=accepted,
            coverage=cov,
            candidates=[(e.id, n, c, v) for e, n, c, v in cands],
        )
