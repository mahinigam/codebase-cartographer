from collections.abc import Iterable
from contextlib import contextmanager

from neo4j import GraphDatabase

from app.core.config import settings
from app.models.graph import CodeFile, CodeSymbol, RepositoryGraph


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
        statements = [
            (
                "CREATE CONSTRAINT repo_path IF NOT EXISTS "
                "FOR (r:Repository) REQUIRE r.root_path IS UNIQUE"
            ),
            "CREATE CONSTRAINT file_key IF NOT EXISTS FOR (f:File) REQUIRE f.key IS UNIQUE",
            "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX file_score IF NOT EXISTS FOR (f:File) ON (f.load_bearing_score)",
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
        for file in graph.files:
            tx.run(
                """
                MATCH (r:Repository {root_path: $root_path})
                MERGE (f:File {key: $key})
                SET f += $props
                MERGE (r)-[:CONTAINS]->(f)
                """,
                root_path=graph.root_path,
                key=f"{graph.root_path}:{file.path}",
                props=_file_props(file, graph.root_path),
            )
        tx.run(
            """
            MATCH (r:Repository {root_path: $root_path})-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[rel:IMPORTS|DEPENDS_ON]->()
            DELETE rel
            """,
            root_path=graph.root_path,
        )
        for symbol in graph.symbols:
            tx.run(
                """
                MATCH (f:File {key: $file_key})
                MERGE (s:Symbol {id: $id})
                SET s += $props
                MERGE (f)-[:DEFINES]->(s)
                """,
                file_key=f"{graph.root_path}:{symbol.file_path}",
                id=symbol.id,
                props=_symbol_props(symbol),
            )
        for edge in graph.imports:
            if edge.target_path:
                tx.run(
                    """
                    MATCH (source:File {key: $source_key})
                    MATCH (target:File {key: $target_key})
                    MERGE (source)-[rel:IMPORTS]->(target)
                    SET rel.target = $target, rel.line_number = $line_number, rel.source = "static"
                    """,
                    source_key=f"{graph.root_path}:{edge.source_path}",
                    target_key=f"{graph.root_path}:{edge.target_path}",
                    target=edge.target,
                    line_number=edge.line_number,
                )
            else:
                tx.run(
                    """
                    MATCH (source:File {key: $source_key})
                    MERGE (dep:ExternalDependency {name: $target})
                    MERGE (source)-[:DEPENDS_ON]->(dep)
                    """,
                    source_key=f"{graph.root_path}:{edge.source_path}",
                    target=edge.target,
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

    def graph_slice(self, limit: int = 80, repo_path: str | None = None) -> dict:
        with self.driver.session() as session:
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
                limit=limit,
                repo_path=repo_path,
            )
            node_rows = [dict(record) for record in nodes]
            ids = [row["id"] for row in node_rows]
            edges = session.run(
                """
                MATCH (a:File)-[r:IMPORTS]->(b:File)
                WHERE a.key IN $ids AND b.key IN $ids
                RETURN a.key AS source, b.key AS target, type(r) AS type
                LIMIT 200
                """,
                ids=ids,
            )
            return {"nodes": node_rows, "edges": [dict(record) for record in edges]}

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
        "file_path": symbol.file_path,
        "name": symbol.name,
        "kind": symbol.kind,
        "signature": symbol.signature,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "complexity": symbol.complexity,
    }


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
