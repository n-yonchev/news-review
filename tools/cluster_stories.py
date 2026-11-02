"""Group articles about the same event into story clusters and rank them.

Approach (borrowed from Kagi News/Kite): multilingual sentence embeddings so English
and Bulgarian headlines about one event land together, agglomerative clustering,
then rank clusters by how many distinct outlets cover them.

Input:  .tmp/articles_filtered.json, data/history.json (optional)
Output: .tmp/clusters.json    — all clusters, ranked
        .tmp/candidates.json  — shortlist for the Claude selection step (headlines only)
Usage:  python tools/cluster_stories.py [--threshold 0.42] [--world 40] [--bg 30]
"""
import argparse
from collections import Counter

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from common import DATA, TMP, load_json, save_json

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
WIRE = {"reuters", "ap"}
# Weight per distinct outlet: wires and big international outlets signal significance.
OUTLET_WEIGHT = {"reuters": 1.4, "ap": 1.4, "bbc": 1.2, "dw": 1.1, "guardian": 1.1}


def embed(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL)
    return model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)


def score(arts: list[dict]) -> float:
    outlets = {a["source"] for a in arts}
    regions = {a["region"] for a in arts}
    s = sum(OUTLET_WEIGHT.get(o, 1.0) for o in outlets)
    if len(regions) == 2:  # covered both abroad and in Bulgaria
        s += 1.5
    return round(s, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.42, help="cosine distance cut-off")
    ap.add_argument("--world", type=int, default=40, help="candidate clusters with world coverage")
    ap.add_argument("--bg", type=int, default=30, help="candidate Bulgaria-only clusters")
    args = ap.parse_args()

    articles = load_json(TMP / "articles_filtered.json", [])
    texts = [f"{a['title']}. {a['summary'][:200]}" for a in articles]
    vectors = embed(texts)
    labels = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=args.threshold
    ).fit_predict(vectors)

    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        groups.setdefault(int(lab), []).append(i)

    history = load_json(DATA / "history.json", {"stories": []})
    past_titles = [s["title_en"] for s in history["stories"]]
    past_vecs = embed(past_titles) if past_titles else None

    clusters = []
    for idxs in groups.values():
        arts = [articles[i] for i in idxs]
        centroid = vectors[idxs].mean(axis=0)
        centroid /= np.linalg.norm(centroid) or 1
        # Most central headline represents the cluster.
        rep = arts[int(np.argmax(vectors[idxs] @ centroid))]
        seen_before = None
        if past_vecs is not None:
            sims = past_vecs @ centroid
            j = int(np.argmax(sims))
            if sims[j] > 0.75:
                seen_before = history["stories"][j]["date"]
        regions = Counter(a["region"] for a in arts)
        clusters.append({
            "headline": rep["title"],
            "score": score(arts),
            "n_outlets": len({a["source"] for a in arts}),
            "regions": dict(regions),
            "seen_before": seen_before,
            "articles": sorted(arts, key=lambda a: a["published"] or ""),
        })

    clusters.sort(key=lambda c: (c["score"], len(c["articles"])), reverse=True)
    for n, c in enumerate(clusters, 1):
        c["id"] = f"c{n:03d}"

    world = [c for c in clusters if c["regions"].get("world")][: args.world]
    bg_only = [c for c in clusters if not c["regions"].get("world")][: args.bg]
    candidates = [
        {
            "id": c["id"],
            "score": c["score"],
            "n_outlets": c["n_outlets"],
            "seen_before": c["seen_before"],
            "articles": [
                {"source": a["source_name"], "region": a["region"], "title": a["title"],
                 "summary": a["summary"][:250]}
                for a in c["articles"][:8]
            ],
        }
        for c in sorted(world + bg_only, key=lambda c: c["id"])
    ]

    save_json(TMP / "clusters.json", clusters)
    save_json(TMP / "candidates.json", candidates)
    multi = sum(1 for c in clusters if c["n_outlets"] > 1)
    print(f"{len(articles)} articles -> {len(clusters)} clusters ({multi} multi-outlet); "
          f"{len(candidates)} candidates -> .tmp/candidates.json")
    for c in clusters[:15]:
        print(f"  {c['id']} score={c['score']:5} outlets={c['n_outlets']:2} {c['headline'][:90]}")


if __name__ == "__main__":
    main()
