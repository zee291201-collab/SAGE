import os
import json
import math
import hashlib
import re
import requests
from pathlib import Path


OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = os.getenv(
    "SAGE_EMBED_MODEL",
    "embeddinggemma"
)

DEFAULT_KNOWLEDGE_DIR = (
    Path(__file__).resolve().parent / "knowledge"
)


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".py",
    ".ino",
    ".yaml",
    ".yml",
    ".pdf",
}


# ============================================================
# TEXT CHUNKING
# ============================================================

def _chunks(text, chunk_size=1200, overlap=200):

    text = text.strip()

    if not text:
        return []

    chunks = []

    start = 0

    while start < len(text):

        end = min(
            len(text),
            start + chunk_size
        )

        piece = text[start:end].strip()

        if piece:
            chunks.append(piece)

        if end >= len(text):
            break

        start = max(
            start + 1,
            end - overlap
        )

    return chunks


# ============================================================
# TEXT CLEANING
# ============================================================

def _clean_text(text):

    if not text:
        return ""

    lines = []

    for line in text.splitlines():

        line = " ".join(
            line.split()
        )

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


# ============================================================
# PDF STRUCTURE DETECTION
# ============================================================

def _detect_structure(lines, current_structure):

    """
    Attempts to identify:

    - chapters
    - sections
    - subsections

    This is intentionally conservative.

    SAGE should prefer UNKNOWN over inventing
    a document structure.
    """

    structure = current_structure.copy()

    for line in lines:

        text = line.strip()

        if not text:
            continue


        # ----------------------------------------------------
        # CHAPTER
        # ----------------------------------------------------

        chapter_match = re.match(
            r"^(?:CHAPTER|Chapter)\s+"
            r"([A-Za-z0-9IVXiv.-]+)"
            r"(?:\s*[-:]\s*|\s+)?"
            r"(.*)$",
            text
        )

        if chapter_match:

            number = chapter_match.group(1)
            title = chapter_match.group(2).strip()

            if title:

                structure["chapter"] = (
                    f"Chapter {number} — {title}"
                )

            else:

                structure["chapter"] = (
                    f"Chapter {number}"
                )

            structure["section"] = ""
            structure["subsection"] = ""

            continue


        # ----------------------------------------------------
        # SECTION NUMBERING
        # ----------------------------------------------------

        section_match = re.match(
            r"^(\d+(?:\.\d+)?)\s+"
            r"(.{3,150})$",
            text
        )

        if section_match:

            number = section_match.group(1)
            title = section_match.group(2).strip()

            # 1.2 = section
            if "." not in number:

                structure["section"] = (
                    f"{number} {title}"
                )

                structure["subsection"] = ""

            # 1.2.3 is handled below
            else:

                parts = number.split(".")

                if len(parts) >= 3:

                    structure["subsection"] = (
                        f"{number} {title}"
                    )

                else:

                    structure["section"] = (
                        f"{number} {title}"
                    )

                    structure["subsection"] = ""

            continue


        # ----------------------------------------------------
        # COMMON SECTION HEADINGS
        # ----------------------------------------------------

        upper = text.upper()

        heading_words = (
            "INTRODUCTION",
            "OVERVIEW",
            "AERODYNAMICS",
            "LIFT",
            "DRAG",
            "AIRFOILS",
            "AIRFOIL DESIGN",
            "PRESSURE DISTRIBUTION",
            "STALL",
            "THRUST",
            "WEIGHT",
            "BALANCE",
            "FLIGHT CONTROLS",
            "PERFORMANCE",
            "MANEUVERING"
        )

        if (
            upper in heading_words
            and len(text) < 100
        ):

            structure["section"] = text
            structure["subsection"] = ""

    return structure


# ============================================================
# PDF EXTRACTION
# ============================================================

def _read_pdf(path):

    """
    Extract a PDF page-by-page.

    Every returned record contains:

        page
        chapter
        section
        subsection
        text

    This allows SAGE to know WHERE information came from.
    """

    try:

        from pypdf import PdfReader

    except ImportError:

        raise RuntimeError(
            "PDF support requires pypdf. "
            "Run: python3 -m pip install pypdf"
        )


    reader = PdfReader(
        str(path)
    )

    pages = []

    structure = {
        "chapter": "",
        "section": "",
        "subsection": ""
    }


    for page_number, page in enumerate(
        reader.pages,
        1
    ):

        raw_text = (
            page.extract_text()
            or ""
        )

        cleaned = _clean_text(
            raw_text
        )

        if not cleaned:
            continue


        lines = cleaned.splitlines()


        # Detect headings on this page
        structure = _detect_structure(
            lines,
            structure
        )


        pages.append({
            "page": page_number,
            "chapter": structure["chapter"],
            "section": structure["section"],
            "subsection": structure["subsection"],
            "text": cleaned
        })


    return pages


# ============================================================
# NORMAL FILE READER
# ============================================================

def _read_file(path):

    try:

        return path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception:

        return ""


# ============================================================
# FILE FINGERPRINT
# ============================================================

def _file_fingerprint(path):

    stat = path.stat()

    return hashlib.sha256(
        (
            f"{path.resolve()}:"
            f"{stat.st_mtime_ns}:"
            f"{stat.st_size}"
        ).encode()
    ).hexdigest()


# ============================================================
# KNOWLEDGE BASE
# ============================================================

class KnowledgeBase:

    """
    Read-only semantic knowledge retrieval.

    The index is stored locally in:

        knowledge/index.json

    Source files are never modified.

    Each record contains location metadata such as:

        source
        page
        chapter
        section
        subsection
        chunk
        text
        embedding
    """


    def __init__(
        self,
        directory=DEFAULT_KNOWLEDGE_DIR
    ):

        self.directory = Path(
            directory
        )

        self.index_file = (
            self.directory / "index.json"
        )

        self.directory.mkdir(
            parents=True,
            exist_ok=True
        )

        self.records = (
            self._load_index()
        )


    # ========================================================
    # LOAD INDEX
    # ========================================================

    def _load_index(self):

        try:

            data = json.loads(
                self.index_file.read_text(
                    encoding="utf-8"
                )
            )

            return (
                data
                if isinstance(data, list)
                else []
            )

        except Exception:

            return []


    # ========================================================
    # SAVE INDEX
    # ========================================================

    def _save_index(self):

        self.index_file.write_text(
            json.dumps(
                self.records,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )


    # ========================================================
    # EMBEDDINGS
    # ========================================================

    def _embed(self, texts):

        if not texts:
            return []

        response = requests.post(
            OLLAMA_EMBED_URL,
            json={
                "model": EMBED_MODEL,
                "input": texts
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "embeddings",
            []
        )


    # ========================================================
    # REBUILD KNOWLEDGE
    # ========================================================

    def rebuild(self):

        files = [
            p
            for p in self.directory.rglob("*")
            if (
                p.is_file()
                and p.suffix.lower()
                in SUPPORTED_EXTENSIONS
                and p.name
                != self.index_file.name
            )
        ]


        new_records = []


        print(
            f"Found {len(files)} knowledge files."
        )


        for path in files:

            relative_source = str(
                path.relative_to(
                    self.directory
                )
            )


            # =================================================
            # PDF
            # =================================================

            if path.suffix.lower() == ".pdf":

                print(
                    f"Reading PDF: "
                    f"{path.name}"
                )


                pages = _read_pdf(
                    path
                )


                if not pages:

                    print(
                        "  Skipped: "
                        "no readable text"
                    )

                    continue


                chunk_number = 0


                for page_data in pages:

                    page_text = (
                        page_data["text"]
                    )


                    chunks = _chunks(
                        page_text
                    )


                    for chunk in chunks:

                        new_records.append({

                            "source":
                                relative_source,

                            "page":
                                page_data["page"],

                            "chapter":
                                page_data[
                                    "chapter"
                                ],

                            "section":
                                page_data[
                                    "section"
                                ],

                            "subsection":
                                page_data[
                                    "subsection"
                                ],

                            "type":
                                "text",

                            "chunk":
                                chunk_number,

                            "text":
                                chunk

                        })


                        chunk_number += 1


                print(
                    f"  Pages: "
                    f"{len(pages)}"
                )

                print(
                    f"  Created "
                    f"{chunk_number} "
                    f"chunks."
                )


            # =================================================
            # NORMAL TEXT FILE
            # =================================================

            else:

                print(
                    f"Reading: "
                    f"{path.name}"
                )


                text = _read_file(
                    path
                )


                if not text:

                    print(
                        "  Skipped: "
                        "no readable text"
                    )

                    continue


                chunks = _chunks(
                    text
                )


                for i, chunk in enumerate(
                    chunks
                ):

                    new_records.append({

                        "source":
                            relative_source,

                        "page":
                            None,

                        "chapter":
                            "",

                        "section":
                            "",

                        "subsection":
                            "",

                        "type":
                            "text",

                        "chunk":
                            i,

                        "text":
                            chunk

                    })


                print(
                    f"  Created "
                    f"{len(chunks)} "
                    f"chunks."
                )


        # =====================================================
        # NOTHING FOUND
        # =====================================================

        if not new_records:

            self.records = []

            self._save_index()

            return 0


        # =====================================================
        # EMBEDDING
        # =====================================================

        print(
            f"\nEmbedding "
            f"{len(new_records)} "
            f"knowledge chunks..."
        )


        batch_size = 16


        for start in range(
            0,
            len(new_records),
            batch_size
        ):

            batch = new_records[
                start:start + batch_size
            ]


            end = min(
                start + batch_size,
                len(new_records)
            )


            print(
                f"Embedding chunks "
                f"{start + 1}-{end} "
                f"of "
                f"{len(new_records)}..."
            )


            embeddings = self._embed(
                [
                    r["text"]
                    for r in batch
                ]
            )


            for record, embedding in zip(
                batch,
                embeddings
            ):

                record[
                    "embedding"
                ] = embedding


        # =====================================================
        # SAVE
        # =====================================================

        self.records = new_records

        self._save_index()


        print(
            f"\nKnowledge index rebuilt: "
            f"{len(self.records)} chunks."
        )


        return len(
            self.records
        )


    # ========================================================
    # COSINE SIMILARITY
    # ========================================================

    def _cosine(self, a, b):

        if (
            not a
            or not b
            or len(a) != len(b)
        ):

            return 0.0


        dot = sum(
            x * y
            for x, y in zip(
                a,
                b
            )
        )


        na = math.sqrt(
            sum(
                x * x
                for x in a
            )
        )


        nb = math.sqrt(
            sum(
                y * y
                for y in b
            )
        )


        return (
            dot / (na * nb)
            if na and nb
            else 0.0
        )


    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query,
        top_k=5,
        threshold=0.55
    ):

        if not self.records:
            return []


        q_embeddings = self._embed(
            [query]
        )


        if not q_embeddings:
            return []


        q_embedding = q_embeddings[0]


        scored = []


        for record in self.records:

            score = self._cosine(
                q_embedding,
                record.get(
                    "embedding",
                    []
                )
            )


            if score >= threshold:

                scored.append({

                    "source":
                        record["source"],

                    "page":
                        record.get(
                            "page"
                        ),

                    "chapter":
                        record.get(
                            "chapter",
                            ""
                        ),

                    "section":
                        record.get(
                            "section",
                            ""
                        ),

                    "subsection":
                        record.get(
                            "subsection",
                            ""
                        ),

                    "type":
                        record.get(
                            "type",
                            "text"
                        ),

                    "chunk":
                        record.get(
                            "chunk"
                        ),

                    "score":
                        round(
                            score,
                            4
                        ),

                    "text":
                        record["text"]

                })


        scored.sort(
            key=lambda x:
                x["score"],
            reverse=True
        )


        return scored[
            :top_k
        ]


    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        return {

            "documents":
                len(
                    set(
                        r["source"]
                        for r in self.records
                    )
                ),

            "chunks":
                len(
                    self.records
                ),

            "embedding_model":
                EMBED_MODEL

        }