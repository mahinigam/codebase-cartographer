from pydantic import BaseModel, Field


class CodeFile(BaseModel):
    path: str
    language: str
    loc: int
    churn_count: int = 0
    last_modified: str | None = None
    complexity: int = 0
    load_bearing_score: float = 0


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


class RepositoryGraph(BaseModel):
    root_path: str
    name: str
    files: list[CodeFile] = Field(default_factory=list)
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports: list[ImportEdge] = Field(default_factory=list)


class ScanRequest(BaseModel):
    path: str


class QueryRequest(BaseModel):
    question: str
    repo_path: str | None = None


class ImpactRequest(BaseModel):
    path: str
    repo_path: str | None = None
    depth: int = Field(default=3, ge=1, le=6)
