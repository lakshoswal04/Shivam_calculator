"""Cryptographic identity for source documents (brief §2)."""
import hashlib
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def doc_id_for(relpath: str, sha256: str) -> str:
    """Stable, human-traceable document id: slug of the filename + hash prefix."""
    stem = Path(relpath).stem.lower()
    slug = "".join(c if c.isalnum() else "-" for c in stem).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug[:48]}-{sha256[:8]}"
