from dataclasses import dataclass
from typing import TypedDict, List
from filter_models import CodeInfo

@dataclass
class Chunk:
    chunk_id: str
    repo: str
    path: str
    language: str
    deps: List[str]
    info: CodeInfo
    content: str