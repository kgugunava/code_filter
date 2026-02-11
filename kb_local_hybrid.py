import json
import os
import argparse
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from tree_sitter_go import language

from code_filter import Filter as CodeFilter


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


_TOKEN_RE = re.compile(r"[A-Za-z_]\w+|\d+|==|!=|<=|>=|->|=>|::|[:(){}\[\].,;]")

def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class Chunk:
    chunk_id: str
    repo: str
    path: str
    language: str
    imports: List[str]
    classes: List[str]
    functions: List[str]
    content: str


class LocalKB:

    def __init__(self, dir_path: str = "./kb_store"):
        self.dir_path = dir_path
        self.chunks_path = os.path.join(dir_path, "chunks.json")
        self.vectors_path = os.path.join(dir_path, "vectors.npy")
        self.bm25_tokens_path = os.path.join(dir_path, "bm25_tokens.json")

        os.makedirs(dir_path, exist_ok=True)

        self.model = SentenceTransformer(MODEL_NAME)

        self.chunks: List[Chunk] = []
        self.vectors: Optional[np.ndarray] = None  # (N, D)

        # BM25
        self.bm25_tokens: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

        self._load()

    #эмбединги
    # возвращает эмбэдинги
    def _embed(self, text: str) -> np.ndarray:
        v = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)

    # загружает чанки, токены и векторы
    def _load(self) -> None:
        if os.path.exists(self.chunks_path):
            with open(self.chunks_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.chunks = [Chunk(**x) for x in raw]
        else:
            self.chunks = []

        if os.path.exists(self.vectors_path):
            self.vectors = np.load(self.vectors_path)
        else:
            self.vectors = None

        if os.path.exists(self.bm25_tokens_path):
            with open(self.bm25_tokens_path, "r", encoding="utf-8") as f:
                self.bm25_tokens = json.load(f)
        else:
            self.bm25_tokens = []

        self._rebuild_bm25()

    def _save(self) -> None:
        with open(self.chunks_path, "w", encoding="utf-8") as f:
            json.dump([asdict(c) for c in self.chunks], f, ensure_ascii=False, indent=2)

        if self.vectors is None:
            np.save(self.vectors_path, np.zeros((0, 384), dtype=np.float32))
        else:
            np.save(self.vectors_path, self.vectors)

        with open(self.bm25_tokens_path, "w", encoding="utf-8") as f:
            json.dump(self.bm25_tokens, f, ensure_ascii=False, indent=2)

    def _rebuild_bm25(self) -> None:
        if self.bm25_tokens and len(self.bm25_tokens) == len(self.chunks):
            self.bm25 = BM25Okapi(self.bm25_tokens)
        else:
            self.bm25 = BM25Okapi(self.bm25_tokens) if self.bm25_tokens else None

    #добавление чанков
    def add_many(self, chunks: List[Chunk]) -> None:
        vecs = [self._embed(c.content) for c in chunks]
        vecs = np.vstack([v.reshape(1, -1) for v in vecs])

        tokens = [tokenize(c.content) for c in chunks]

        self.chunks.extend(chunks)
        self.bm25_tokens.extend(tokens)

        if self.vectors is None:
            self.vectors = vecs
        else:
            self.vectors = np.vstack([self.vectors, vecs])

        self._rebuild_bm25()
        self._save()

    # #фильтры
    # def _filter_mask(
    #     self,
    #     language: Optional[str],
    #     dep_any: Optional[List[str]],
    # ) -> np.ndarray:
    #     n = len(self.chunks)
    #     mask = np.ones(n, dtype=bool)

    #     if language is not None:
    #         mask &= np.array([c.language == language for c in self.chunks], dtype=bool)

    #     if dep_any is not None:
    #         dep_any_set = set(dep_any)
    #         mask &= np.array(
    #             [len(dep_any_set.intersection(set(c.deps))) > 0 for c in self.chunks],
    #             dtype=bool,
    #         )

    #     return mask

    # # функция которая возвращает массив индексов после фильтрации
    # def _get_filtered_indices(
    #     self,
    #     language: Optional[str],
    #     dep_any: Optional[List[str]],
    #     ) -> np.ndarray:
    #     """Возвращает массив индексов чанков, прошедших фильтрацию."""
    #     indices = []
    #     dep_any_set = set(dep_any) if dep_any else None

    #     for i, c in enumerate(self.chunks):
    #         if language is not None and c.language != language:
    #             continue
    #         if dep_any_set is not None:
    #             if not dep_any_set.intersection(c.deps):
    #                 continue
    #         indices.append(i)
        
    #     return np.array(indices, dtype=np.int32)
    

    def get_filtered_chunks(
        self,
        language: Optional[str] = None,
        imports: Optional[List[str]] = None,
        classes: Optional[List[str]] = None,
        functions: Optional[List[str]] = None
    ) -> List[Chunk]:
        """
        Возвращает чанки, соответствующие:
        - языку (обязательно, если задан),
        - хотя бы одному из импортов (обязательно, если список непустой).
        
        Поля classes и functions НЕ используются для фильтрации (мягкие).
        """
        filtered = self.chunks

        # Обязательный фильтр: язык
        if language is not None:
            filtered = [c for c in filtered if c.language == language]

        # Обязательный фильтр: импорты (только если список непустой)
        if imports:  # imports не None и не пустой список
            imports_set = set(imports)
            filtered = [
                c for c in filtered
                if imports_set.intersection(c.imports)
            ]

        # classes и functions — игнорируются (мягкие фильтры)

        return filtered

    # #поиск векторов 
    # def search_vector(
    #     self,
    #     query: str,
    #     k: int = 5,
    #     language: Optional[str] = None,
    #     dep_any: Optional[List[str]] = None,
    # ) -> List[Dict[str, Any]]:
    #     if not self.chunks or self.vectors is None:
    #         return []

    #     # ← ФИЛЬТРАЦИЯ ДО ВЫЧИСЛЕНИЙ
    #     idx = self._get_filtered_indices(language, dep_any)
    #     if idx.size == 0:
    #         return []

    #     # Работаем ТОЛЬКО с отфильтрованными векторами
    #     filtered_vectors = self.vectors[idx]
    #     q = self._embed(query)
    #     sims = (filtered_vectors @ q).astype(np.float32)

    #     # Выбираем топ-k среди отфильтрованных
    #     top_local = np.argsort(-sims)[:k]
    #     top_idx = idx[top_local]  # восстанавливаем оригинальные индексы

    #     return [self._as_result(i, float(sims[j]), "vector") for j, i in enumerate(top_idx)]

    # #BM25 поиск
    # def search_bm25(
    #     self,
    #     query: str,
    #     k: int = 5,
    #     language: Optional[str] = None,
    #     dep_any: Optional[List[str]] = None,
    # ) -> List[Dict[str, Any]]:
    #     if not self.chunks or self.bm25 is None:
    #         return []

    #     idx = self._get_filtered_indices(language, dep_any)
    #     if idx.size == 0:
    #         return []

    #     # Фильтруем токены и пересоздаём BM25 (или используем предварительно отфильтрованный)
    #     filtered_tokens = [self.bm25_tokens[i] for i in idx]
    #     filtered_bm25 = BM25Okapi(filtered_tokens)

    #     q_tokens = tokenize(query)
    #     scores = np.array(filtered_bm25.get_scores(q_tokens), dtype=np.float32)

    #     top_local = np.argsort(-scores)[:k]
    #     top_idx = idx[top_local]

    #     return [self._as_result(i, float(scores[j]), "bm25") for j, i in enumerate(top_idx)]

    # #гибрид ррф
    # def search_hybrid(
    #     self,
    #     query: str,
    #     k: int = 5,
    #     language: Optional[str] = None,
    #     dep_any: Optional[List[str]] = None,
    #     candidates: int = 50,
    #     rrf_k: int = 60,
    # ) -> List[Dict[str, Any]]:
    #     bm = self.search_bm25(query, k=candidates, language=language, dep_any=dep_any)
    #     ve = self.search_vector(query, k=candidates, language=language, dep_any=dep_any)

    #     bm_rank = {r["chunk_id"]: i + 1 for i, r in enumerate(bm)}
    #     ve_rank = {r["chunk_id"]: i + 1 for i, r in enumerate(ve)}

    #     all_ids = set(bm_rank.keys()) | set(ve_rank.keys())
    #     if not all_ids:
    #         return []

    #     # посчитаем rrf
    #     scored: List[Tuple[str, float]] = []
    #     for cid in all_ids:
    #         s = 0.0
    #         if cid in bm_rank:
    #             s += 1.0 / (rrf_k + bm_rank[cid])
    #         if cid in ve_rank:
    #             s += 1.0 / (rrf_k + ve_rank[cid])
    #         scored.append((cid, s))

    #     scored.sort(key=lambda x: x[1], reverse=True)
    #     top_ids = [cid for cid, _ in scored[:k]]

    #     id_to_index = {c.chunk_id: i for i, c in enumerate(self.chunks)}
    #     results = []
    #     for cid in top_ids:
    #         i = id_to_index[cid]
    #         results.append(
    #             {
    #                 **self._as_result(i, float(next(s for _cid, s in scored if _cid == cid)), "hybrid"),
    #                 "bm25_rank": bm_rank.get(cid),
    #                 "vector_rank": ve_rank.get(cid),
    #             }
    #         )
    #     return results

    # def _as_result(self, i: int, score: float, source: str) -> Dict[str, Any]:
    #     c = self.chunks[i]
    #     return {
    #         "source": source,
    #         "score": score,
    #         "chunk_id": c.chunk_id,
    #         "repo": c.repo,
    #         "path": c.path,
    #         "language": c.language,
    #         "deps": c.deps,
    #         "content": c.content,
    #     }
    
    def print_filtered_chunks(
        self,
        language: Optional[str] = None,
        imports: Optional[List[str]] = None,
        classes: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
    ) -> None:
        """Печатает отфильтрованные чанки в человекочитаемом виде."""
        chunks = self.get_filtered_chunks(language=language, imports=imports, classes=classes, functions=functions)
        
        print(f"\nНайдено {len(chunks)} чанков:")
        print("=" * 80)
        
        if not chunks:
            print("Нет результатов")
            return

        for i, c in enumerate(chunks, 1):
            print(f"\n--- Чанк {i} ---")
            print(f"ID:       {c.chunk_id}")
            print(f"Язык:     {c.language}")
            print(f"Зависимости: {c.imports}")
            print(f"Репо/путь: {c.repo} :: {c.path}")
            print(f"Контент:\n{c.content[:200]}{'...' if len(c.content) > 200 else ''}")


def print_results(title: str, results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    if not results:
        print("Нет результатов")
        return
    for r in results:
        header = f'{r["source"]:6s} score={r["score"]:.4f} id={r["chunk_id"]} lang={r["language"]} deps={r["deps"]}'
        extra = ""
        if r["source"] == "hybrid":
            extra = f' (bm25_rank={r.get("bm25_rank")}, vec_rank={r.get("vector_rank")})'
        print("\n--- " + header + extra)
        print(f'{r["repo"]} :: {r["path"]}')
        print(r["content"])



def cli():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo")

    p_add = sub.add_parser("add")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--repo", required=True)
    p_add.add_argument("--path", required=True)
    p_add.add_argument("--lang", required=True)
    p_add.add_argument("--deps", default="")
    p_add.add_argument("--file", required=True, help="путь к файлу с кодом (текст чанка)")

    p_search = sub.add_parser("search")
    p_search.add_argument("--mode", choices=["bm25", "vector", "hybrid"], default="hybrid")
    p_search.add_argument("--q", required=True)
    p_search.add_argument("--k", type=int, default=5)
    p_search.add_argument("--lang", default=None)
    p_search.add_argument("--dep", action="append", default=None, help="можно указать несколько раз: --dep httpx --dep fastapi")

    p_filter = sub.add_parser("filter")
    p_filter.add_argument("--language")
    p_filter.add_argument("--imports")
    p_filter.add_argument("--classes")
    p_filter.add_argument("--functions")

    p_analyze = sub.add_parser("analyze")
    p_analyze.add_argument("--file", required=True, help="Путь к файлу для анализа")

    args = parser.parse_args()

    kb = LocalKB("./kb_store")

    print(len(kb.chunks))

    # if args.cmd == "demo":
    #     demo() 
    #     return

    # if args.cmd == "add":
    #     with open(args.file, "r", encoding="utf-8") as f:
    #         content = f.read()
    #     deps = [d.strip() for d in args.deps.split(",") if d.strip()]
    #     kb.add_many([Chunk(
    #         chunk_id=args.id,
    #         repo=args.repo,
    #         path=args.path,
    #         language=args.lang,
    #         deps=deps,
    #         content=content
    #     )])
    #     print(f"OK: added chunk {args.id}")
    #     return

    # if args.cmd == "search":
    #     dep_any = args.dep if args.dep else None
    #     if args.mode == "bm25":
    #         res = kb.search_bm25(args.q, k=args.k, language=args.lang, dep_any=dep_any)
    #     elif args.mode == "vector":
    #         res = kb.search_vector(args.q, k=args.k, language=args.lang, dep_any=dep_any)
    #     else:
    #         res = kb.search_hybrid(args.q, k=args.k, language=args.lang, dep_any=dep_any)

    #     print_results(f"SEARCH mode={args.mode} q='{args.q}'", res)

    if args.cmd == "filter":
        language = args.language
        imports = []
        classes = []
        functions = []
        if args.imports is not None:
            imports = [i.strip() for i in args.imports.split(",") if i.strip()]
        if args.classes is not None:
            classes = [i.strip() for i in args.classes.split(",") if i.strip()]
        if args.functions is not None:
            functions = [i.strip() for i in args.functions.split(",") if i.strip()]
        print(kb.print_filtered_chunks(language=language, imports=imports, classes=classes, functions=functions))

    if args.cmd == "analyze":
    # 1. Анализируем файл через code_filter
        

        # Определяем язык по расширению
        ext = os.path.splitext(args.file)[1].lower()
        lang_map = {".py": "python", ".go": "go", ".js": "javascript"}
        language = lang_map.get(ext, "python")

        code_filter = CodeFilter(language)
        context = code_filter.extract_context(args.file)  # ← ваш метод

        print(context)

        kb.print_filtered_chunks(
            language=context["language"],
            imports=context["imports"],
            classes=[],
            functions=[]
        )


# def demo():
#     """
#     Демонстрация работы LocalKB:
#     1) Если база пустая — добавляем 3 демо-чанка
#     2) Показываем BM25 / Vector / Hybrid
#     3) Показываем фильтрацию по метаданным (language, deps) 
#     """

#     kb = LocalKB("./kb_store")

#     if len(kb.chunks) == 0:
#         kb.add_many([
#             Chunk(
#                 chunk_id="ch_jwt_py",
#                 repo="myorg/payments-service",
#                 path="src/auth/jwt.py",
#                 language="python",
#                 deps=["fastapi", "python-jose"],
#                 content="""from jose import jwt

# def verify_jwt(token: str, key: str) -> dict:
#     return jwt.decode(token, key, algorithms=["HS256"])
# """
#             ),
#             Chunk(
#                 chunk_id="ch_retry_py",
#                 repo="myorg/payments-service",
#                 path="src/utils/retry.py",
#                 language="python",
#                 deps=["httpx"],
#                 content="""import asyncio

# async def retry_async(fn, attempts=3, delay=0.5):
#     for i in range(attempts):
#         try:
#             return await fn()
#         except Exception:
#             if i == attempts - 1:
#                 raise
#             await asyncio.sleep(delay)
# """
#             ),
#             Chunk(
#                 chunk_id="ch_httpx_client",
#                 repo="myorg/payments-service",
#                 path="src/http/client.py",
#                 language="python",
#                 deps=["httpx"],
#                 content="""import httpx

# def make_client(timeout_s: float = 5.0) -> httpx.Client:
#     return httpx.Client(timeout=timeout_s)
# """
#             ),
#         ])
#         print("Добавил демо-чанки в kb_store/")

#     q1 = "from jose import jwt decode HS256"
#     res = kb.search_bm25(q1, k=3, language="python", dep_any=["fastapi"])
#     print_results(f"DEMO BM25 (точные токены): q='{q1}'", res)

#     q2 = "как проверить jwt токен и достать payload"
#     res = kb.search_vector(q2, k=3, language="python")
#     print_results(f"DEMO VECTOR (по смыслу): q='{q2}'", res)

#     q3 = "jwt decode как проверить токен HS256"
#     res = kb.search_hybrid(q3, k=3, language="python")
#     print_results(f"DEMO HYBRID (RRF): q='{q3}'", res)

#     q4 = "http client timeout"
#     res = kb.search_hybrid(q4, k=5, language="python", dep_any=["httpx"])
#     print_results(f"DEMO FILTER deps=httpx: q='{q4}'", res)


if __name__ == "__main__":
    cli()

