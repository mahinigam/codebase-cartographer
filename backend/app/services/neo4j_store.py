from collections.abc import Iterable, Sequence
from contextlib import contextmanager

from neo4j import GraphDatabase

from app.core.config import settings
from app.models.graph import CodeFile, CodeSymbol, RepositoryGraph

WRITE_BATCH_SIZE = 250
GRAPH_DEFAULT_NODE_LIMIT = 80
GRAPH_MAX_NODE_LIMIT = 400
GRAPH_DEFAULT_EDGE_LIMIT = 200
GRAPH_MAX_EDGE_LIMIT = 2000


class Neo4jStore:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def close(self) -> None:
        self.driver.close()

    def ping(self) -> bool:
        with self.driver.session() as session:
            return bool(session.run("RETURN 1 AS ok").single()["ok"])

    def ensure_schema(self) -> None:
        vector_dimensions = int(settings.embedding_dimensions)
        if vector_dimensions < 1 or vector_dimensions > 4096:
            raise ValueError("embedding_dimensions must be between 1 and 4096")
        vector_index = (
            "CREATE VECTOR INDEX summary_embedding IF NOT EXISTS "
            "FOR (s:Summary) ON (s.embedding) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {vector_dimensions}, "
            "`vector.similarity_function`: 'cosine'}}"
        )
        statements = [
            (
                "CREATE CONSTRAINT repo_path IF NOT EXISTS "
                "FOR (r:Repository) REQUIRE r.root_path IS UNIQUE"
            ),
            "CREATE CONSTRAINT file_key IF NOT EXISTS FOR (f:File) REQUIRE f.key IS UNIQUE",
            "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT summary_key IF NOT EXISTS FOR (s:Summary) REQUIRE s.key IS UNIQUE",
            "CREATE INDEX file_score IF NOT EXISTS FOR (f:File) ON (f.load_bearing_score)",
            vector_index,
        ]
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement)

    def upsert_repository_graph(self, graph: RepositoryGraph) -> None:
        self.ensure_schema()
        with self.driver.session() as session:
            session.execute_write(self._write_graph, graph)

    @staticmethod
    def _write_graph(tx, graph: RepositoryGraph) -> None:
        tx.run(
            """
            MERGE (r:Repository {root_path: $root_path})
            SET r.name = $name, r.indexed_at = datetime()
            """,
            root_path=graph.root_path,
            name=graph.name,
        )
        file_rows = [
            {
                "key": f"{graph.root_path}:{file.path}",
                "props": _file_props(file, graph.root_path),
            }
            for file in graph.files
        ]
        for batch in _batched(file_rows):
            tx.run(
                """
                MATCH (r:Repository {root_path: $root_path})
                UNWIND $files AS file
                MERGE (f:File {key: file.key})
                SET f += file.props
                MERGE (r)-[:CONTAINS]->(f)
                """,
                root_path=graph.root_path,
                files=batch,
            )
        tx.run(
            """
            MATCH (r:Repository {root_path: $root_path})-[:CONTAINS]->(f:File)
            WHERE NOT f.key IN $keys
            OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
            OPTIONAL MATCH (f)-[:SUMMARIZES]->(sum:Summary)
            DETACH DELETE s, sum, f
            """,
            root_path=graph.root_path,
            keys=[row["key"] for row in file_rows],
        )
        tx.run(
            """
            MATCH (r:Repository {root_path: $root_path})-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[rel:IMPORTS|DEPENDS_ON]->()
            DELETE rel
            """,
            root_path=graph.root_path,
        )
        tx.run(
            """
            MATCH (r:Repository {root_path: $root_path})-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
            DETACH DELETE s
            """,
            root_path=graph.root_path,
        )
        symbol_rows = [
            {
                "file_key": f"{graph.root_path}:{symbol.file_path}",
                "id": _symbol_key(graph.root_path, symbol),
                "props": _symbol_props(symbol),
            }
            for symbol in graph.symbols
        ]
        for batch in _batched(symbol_rows):
            tx.run(
                """
                UNWIND $symbols AS symbol
                MATCH (f:File {key: symbol.file_key})
                MERGE (s:Symbol {id: symbol.id})
                SET s += symbol.props
                MERGE (f)-[:DEFINES]->(s)
                """,
                symbols=batch,
            )
        import_rows, dep_rows = _import_batches(graph)
        for batch in _batched(import_rows):
            tx.run(
                """
                UNWIND $imports AS edge
                MATCH (source:File {key: edge.source_key})
                MATCH (target:File {key: edge.target_key})
                MERGE (source)-[rel:IMPORTS]->(target)
                SET rel.target = edge.target,
                    rel.line_number = edge.line_number,
                    rel.source = "static"
                """,
                imports=batch,
            )
        for batch in _batched(dep_rows):
            tx.run(
                """
                UNWIND $deps AS edge
                MATCH (source:File {key: edge.source_key})
                MERGE (dep:ExternalDependency {name: edge.target})
                MERGE (source)-[:DEPENDS_ON]->(dep)
                """,
                deps=batch,
            )
        tx.run(
            """
            MATCH (dep:ExternalDependency)
            WHERE NOT ()-[:DEPENDS_ON]->(dep)
            DETACH DELETE dep
            """
        )

    def repositories(self) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Repository)
                OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
                RETURN r.name AS name, r.root_path AS root_path,
                       count(DISTINCT f) AS files, toString(r.indexed_at) AS indexed_at
                ORDER BY indexed_at DESC
                """
            )
            return [dict(record) for record in result]

    def overview(self, repo_path: str | None = None) -> dict:
        with self.driver.session() as session:
            record = session.run(
                """
                MATCH (r:Repository)
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
                OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
                RETURN count(DISTINCT r) AS repos,
                       count(DISTINCT f) AS files,
                       count(DISTINCT s) AS symbols,
                       coalesce(round(avg(f.load_bearing_score), 2), 0) AS avg_score
                """,
                repo_path=repo_path,
            ).single()
            return dict(record) if record else {}

    def top_load_bearing_files(self, limit: int = 10, repo_path: str | None = None) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(f:File)
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                RETURN f.path AS path, f.language AS language, f.loc AS loc,
                       f.complexity AS complexity, f.churn_count AS churn_count,
                       f.load_bearing_score AS load_bearing_score
                ORDER BY f.load_bearing_score DESC
                LIMIT $limit
                """,
                limit=limit,
                repo_path=repo_path,
            )
            return [dict(record) for record in result]

    def graph_slice(
        self,
        limit: int = GRAPH_DEFAULT_NODE_LIMIT,
        edge_limit: int = GRAPH_DEFAULT_EDGE_LIMIT,
        repo_path: str | None = None,
    ) -> dict:
        node_limit, edge_cap = clamp_graph_limits(limit, edge_limit)
        with self.driver.session() as session:
            total_record = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(f:File)
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                RETURN count(f) AS total
                """,
                repo_path=repo_path,
            ).single()
            total_files = int(total_record["total"]) if total_record else 0
            nodes = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(f:File)
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                RETURN f.key AS id, f.path AS label,
                       f.load_bearing_score AS score, labels(f) AS labels,
                       f.root_path AS repo_path
                ORDER BY f.load_bearing_score DESC
                LIMIT $limit
                """,
                limit=node_limit,
                repo_path=repo_path,
            )
            node_rows = [dict(record) for record in nodes]
            ids = [row["id"] for row in node_rows]
            edge_record = session.run(
                """
                MATCH (a:File)-[rel:IMPORTS]->(b:File)
                WHERE a.key IN $ids AND b.key IN $ids
                WITH count(rel) AS total
                RETURN total
                """,
                ids=ids,
            ).single()
            total_edges = int(edge_record["total"]) if edge_record else 0
            edges = session.run(
                """
                MATCH (a:File)-[r:IMPORTS]->(b:File)
                WHERE a.key IN $ids AND b.key IN $ids
                RETURN a.key AS source, b.key AS target, type(r) AS type
                LIMIT $edge_limit
                """,
                ids=ids,
                edge_limit=edge_cap,
            )
            return {
                "nodes": node_rows,
                "edges": [dict(record) for record in edges],
                "total_files": total_files,
                "total_edges": total_edges,
                "truncated": total_files > len(node_rows) or total_edges > edge_cap,
                "node_limit": node_limit,
                "edge_limit": edge_cap,
            }

    def file_paths(self, repo_path: str) -> list[str]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Repository {root_path: $repo_path})-[:CONTAINS]->(f:File)
                RETURN f.path AS path
                ORDER BY f.load_bearing_score DESC, f.path
                """,
                repo_path=repo_path,
            )
            return [record["path"] for record in result]

    def upsert_file_summary(
        self,
        repo_path: str,
        file_path: str,
        summary_text: str,
        embedding: list[float] | None,
        model: str,
        provider: str,
    ) -> None:
        key = f"{repo_path}:{file_path}"
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:Repository {root_path: $repo_path})
                MATCH (r)-[:CONTAINS]->(f:File {path: $file_path})
                MERGE (s:Summary {key: $key})
                SET s.text = $text,
                    s.model = $model,
                    s.provider = $provider,
                    s.repo_path = $repo_path,
                    s.file_path = $file_path,
                    s.updated_at = datetime(),
                    s.embedding = $embedding
                MERGE (f)-[:SUMMARIZES]->(s)
                """,
                repo_path=repo_path,
                file_path=file_path,
                key=key,
                text=summary_text,
                model=model,
                provider=provider,
                embedding=embedding,
            )

    def semantic_search(
        self, embedding: list[float], limit: int = 6, repo_path: str | None = None
    ) -> list[dict]:
        if not embedding:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes('summary_embedding', $limit, $embedding)
                YIELD node, score
                WHERE $repo_path IS NULL OR node.repo_path = $repo_path
                RETURN node.file_path AS path, node.text AS summary, score
                ORDER BY score DESC
                """,
                embedding=embedding,
                limit=limit,
                repo_path=repo_path,
            )
            return [dict(record) for record in result]

    def impact_for_file(
        self, path: str, depth: int = 3, repo_path: str | None = None
    ) -> dict:
        with self.driver.session() as session:
            direct = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(target:File {path: $path})
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                OPTIONAL MATCH (dependent:File)-[:IMPORTS]->(target)
                WHERE dependent IS NULL OR dependent.root_path = target.root_path
                RETURN collect(DISTINCT dependent.path) AS direct_dependents
                """,
                path=path,
                repo_path=repo_path,
            ).single()
            transitive = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(target:File {path: $path})
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                MATCH path=(dependent:File)-[:IMPORTS*1..6]->(target)
                WHERE length(path) <= $depth AND dependent.root_path = target.root_path
                RETURN DISTINCT dependent.path AS path, length(path) AS distance
                ORDER BY distance, path
                LIMIT 100
                """,
                path=path,
                depth=depth,
                repo_path=repo_path,
            )
            return {
                "target": path,
                "repo_path": repo_path,
                "direct_dependents": direct["direct_dependents"] if direct else [],
                "transitive_dependents": [dict(record) for record in transitive],
            }

    def file_detail(self, path: str, repo_path: str | None = None) -> dict:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(f:File {path: $path})
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                WITH f, r
                ORDER BY r.indexed_at DESC
                LIMIT 1
                OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
                OPTIONAL MATCH (f)-[out:IMPORTS]->(imported:File)
                OPTIONAL MATCH (dependent:File)-[:IMPORTS]->(f)
                OPTIONAL MATCH (f)-[:DEPENDS_ON]->(dep:ExternalDependency)
                OPTIONAL MATCH (f)-[:SUMMARIZES]->(sum:Summary)
                RETURN f.path AS path, f.language AS language, f.loc AS loc,
                       f.complexity AS complexity, f.churn_count AS churn_count,
                       f.last_modified AS last_modified,
                       f.load_bearing_score AS load_bearing_score,
                       collect(DISTINCT {name: s.name, kind: s.kind,
                               signature: s.signature, start_line: s.start_line,
                               end_line: s.end_line}) AS symbols,
                       collect(DISTINCT imported.path) AS imports,
                       collect(DISTINCT dependent.path) AS dependents,
                       collect(DISTINCT dep.name) AS external_deps,
                       head(collect(DISTINCT sum.text)) AS summary
                """,
                path=path,
                repo_path=repo_path,
            ).single()
            if not result:
                return {}
            data = dict(result)
            data["symbols"] = [s for s in data["symbols"] if s.get("name")]
            return data

    def search_files(
        self, query: str, limit: int = 8, repo_path: str | None = None
    ) -> list[dict]:
        words = _search_words(query)
        if not words:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Repository)-[:CONTAINS]->(f:File)
                WHERE $repo_path IS NULL OR r.root_path = $repo_path
                OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
                OPTIONAL MATCH (f)-[out:IMPORTS]->(imported:File)
                OPTIONAL MATCH (dependent:File)-[incoming:IMPORTS]->(f)
                OPTIONAL MATCH (f)-[:DEPENDS_ON]->(dep:ExternalDependency)
                WITH f,
                     collect(DISTINCT s.name) AS symbols,
                     collect(DISTINCT imported.path) AS imports,
                     collect(DISTINCT dependent.path) AS dependents,
                     collect(DISTINCT dep.name) AS external_deps
                WITH f, symbols, imports, dependents, external_deps,
                     [word IN $words WHERE
                        toLower(f.path) CONTAINS word OR
                        any(symbol IN symbols WHERE toLower(symbol) CONTAINS word) OR
                        any(path IN imports WHERE toLower(path) CONTAINS word) OR
                        any(path IN dependents WHERE toLower(path) CONTAINS word) OR
                        any(dep IN external_deps WHERE toLower(dep) CONTAINS word)
                     ] AS matched_words
                WHERE size(matched_words) > 0
                RETURN f.path AS path, f.language AS language,
                       symbols[..8] AS symbols,
                       imports[..8] AS imports,
                       dependents[..8] AS dependents,
                       external_deps[..8] AS external_deps,
                       f.load_bearing_score AS load_bearing_score,
                       matched_words AS matched_words
                ORDER BY size(matched_words) DESC, f.load_bearing_score DESC
                LIMIT $limit
                """,
                words=words,
                limit=limit,
                repo_path=repo_path,
            )
            return [dict(record) for record in result]


def clamp_graph_limits(
    node_limit: int, edge_limit: int
) -> tuple[int, int]:
    return (
        max(1, min(int(node_limit), GRAPH_MAX_NODE_LIMIT)),
        max(1, min(int(edge_limit), GRAPH_MAX_EDGE_LIMIT)),
    )


def _batched(items: Sequence, size: int = WRITE_BATCH_SIZE) -> Iterable[list]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _import_batches(graph: RepositoryGraph) -> tuple[list[dict], list[dict]]:
    import_rows: list[dict] = []
    dep_rows: list[dict] = []
    for edge in graph.imports:
        source_key = f"{graph.root_path}:{edge.source_path}"
        if edge.target_path:
            import_rows.append(
                {
                    "source_key": source_key,
                    "target_key": f"{graph.root_path}:{edge.target_path}",
                    "target": edge.target,
                    "line_number": edge.line_number,
                }
            )
        else:
            dep_rows.append({"source_key": source_key, "target": edge.target})
    return import_rows, dep_rows


def _file_props(file: CodeFile, root_path: str) -> dict:
    return {
        "root_path": root_path,
        "path": file.path,
        "language": file.language,
        "loc": file.loc,
        "churn_count": file.churn_count,
        "last_modified": file.last_modified,
        "complexity": file.complexity,
        "load_bearing_score": file.load_bearing_score,
    }


def _symbol_props(symbol: CodeSymbol) -> dict:
    return {
        "local_id": symbol.id,
        "file_path": symbol.file_path,
        "name": symbol.name,
        "kind": symbol.kind,
        "signature": symbol.signature,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "complexity": symbol.complexity,
    }


def _symbol_key(root_path: str, symbol: CodeSymbol) -> str:
    return f"{root_path}:{symbol.id}"


def _search_words(query: str) -> list[str]:
    cleaned = "".join(character.lower() if character.isalnum() else " " for character in query)
    stop_words = {
        "the",
        "and",
        "are",
        "what",
        "which",
        "where",
        "files",
        "file",
        "this",
        "that",
        "codebase",
        "mention",
        "mentions",
        "with",
        "from",
    }
    return sorted({word for word in cleaned.split() if len(word) > 2 and word not in stop_words})


@contextmanager
def neo4j_store() -> Iterable[Neo4jStore]:
    store = Neo4jStore()
    try:
        yield store
    finally:
        store.close()
