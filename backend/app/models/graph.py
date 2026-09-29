from dataclasses import dataclass

from pydantic import BaseModel, Field


class CodeFile(BaseModel):
    path: str
    language: str
    loc: int
    size_bytes: int = 0
    mtime_ns: int = 0
    content_hash: str | None = None
    churn_count: int = 0
    last_modified: str | None = None
    complexity: int = 0
    load_bearing_score: float = 0
    # Jev-derived fields (Bond 1, 2, 3, 8, 10)
    architectural_role: str | None = None
    architectural_role_confidence: float = 0.0
    is_test_file: bool = False
    is_test_probability: float = 0.0
    test_category: str | None = None
    framework: str | None = None
    framework_confidence: float = 0.0
    architecture_layer: str | None = None
    semantic_risk_score: float | None = None
    risk_category: str | None = None
    is_dead_code: bool = False
    is_dead_code_probability: float = 0.0
    dead_code_category: str | None = None
    needs_summary: bool = True
    summary_priority: float = 5.0


class CodeSymbol(BaseModel):
    id: str
    file_path: str
    name: str
    kind: str
    signature: str | None = None
    start_line: int
    end_line: int
    complexity: int = 0


class ImportEdge(BaseModel):
    source_path: str
    target: str
    target_path: str | None = None
    line_number: int | None = None


@dataclass(frozen=True)
class CachedFile:
    file: CodeFile
    symbols: list[CodeSymbol]
    imports: list[ImportEdge]


class RepositoryGraph(BaseModel):
    root_path: str
    name: str
    files: list[CodeFile] = Field(default_factory=list)
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports: list[ImportEdge] = Field(default_factory=list)


class ScanRequest(BaseModel):
    path: str
    summarize: bool = False
    incremental: bool = True


class QueryRequest(BaseModel):
    question: str
    repo_path: str | None = None


class ImpactRequest(BaseModel):
    path: str
    repo_path: str | None = None
    depth: int = Field(default=3, ge=1, le=6)


class SummaryRequest(BaseModel):
    repo_path: str
    max_files: int | None = Field(default=None, ge=1, le=500)
