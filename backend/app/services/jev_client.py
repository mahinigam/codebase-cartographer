"""
TypeSafe Jev decision client for Codebase Cartographer.

Provides typed wrappers around Jev's three primitives (Choice, Noul, Score)
for all 10 integration bonds. Falls back gracefully when Jev is unavailable.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class JevDecision:
    """Parsed result from a single Jev question."""
    def __init__(self, raw: dict):
        self.answer = raw.get("answer")            # For Choice
        self.probability = raw.get("probability")  # For Noul
        self.value = raw.get("value")              # For Score
        self.confidence = raw.get("confidence", 0.0)
        self.distribution = raw.get("distribution", {})  # Full prob per option

    def __repr__(self) -> str:
        parts = []
        if self.answer is not None:
            parts.append(f"answer={self.answer!r}")
        if self.probability is not None:
            parts.append(f"probability={self.probability:.3f}")
        if self.value is not None:
            parts.append(f"value={self.value:.2f}")
        parts.append(f"confidence={self.confidence:.3f}")
        return f"JevDecision({', '.join(parts)})"


class JevResult:
    """Container for multi-question Jev response."""
    def __init__(self, decisions: dict[str, JevDecision]):
        self._decisions = decisions

    def __getattr__(self, name: str) -> JevDecision:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._decisions:
            return self._decisions[name]
        raise AttributeError(f"No decision named {name!r}")

    def get(self, name: str, default: Any = None) -> JevDecision | Any:
        return self._decisions.get(name, default)


class JevClient:
    """HTTP client for the TypeSafe Jev System One API."""

    def __init__(self):
        self.api_key = settings.jev_api_key
        self.base_url = settings.jev_base_url
        self.model = settings.jev_model
        self.enabled = bool(self.api_key)

    async def decide(
        self,
        state: dict | str,
        questions: dict[str, dict],
        timeout: float = 10.0,
    ) -> JevResult | None:
        """
        Send state + questions to Jev and return structured decisions.

        Args:
            state: The context Jev evaluates (can be dict or text).
            questions: Map of question_name -> question_spec.
                       Each spec has "type" (choice/noul/score) and type-specific fields.
            timeout: HTTP timeout in seconds.

        Returns:
            JevResult with named decisions, or None if Jev is unavailable.
        """
        if not self.enabled:
            return None

        payload = {
            "model": self.model,
            "state": state,
            "questions": questions,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/systemone",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Jev API HTTP error %s: %s", exc.response.status_code, exc)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Jev API request failed: %s", exc)
            return None

        data = response.json()
        answers = data.get("answers", data.get("decisions", {}))
        decisions = {
            name: JevDecision(value) for name, value in answers.items()
        }
        return JevResult(decisions)

    # ── Bond-specific helper methods ──────────────────────────────────

    async def classify_file(
        self,
        file_path: str,
        language: str,
        loc: int,
        complexity: int,
        fan_in: int,
        fan_out: int,
        symbols: list[str],
        imports: list[str],
        external_deps: list[str],
        snippet: str = "",
    ) -> JevResult | None:
        """Bond 1: Classify a file's architectural role."""
        state = {
            "file_path": file_path,
            "language": language,
            "loc": loc,
            "complexity": complexity,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "symbols": symbols[:30],
            "imports": imports[:20],
            "external_deps": external_deps[:20],
            "source_snippet": snippet[:2000],
        }
        questions = {
            "architectural_role": {
                "type": "choice",
                "question": (
                    "Analyze this source file's structural metadata and source snippet. "
                    "What is the primary architectural role this file plays in the codebase? "
                    "Consider the file path, the symbols it defines, its import/export patterns, "
                    "its complexity, and its position in the dependency graph (fan-in/fan-out)."
                ),
                "options": [
                    "core-business-logic",
                    "api-endpoint-handler",
                    "api-route-definition",
                    "middleware",
                    "authentication-authorization",
                    "data-model-schema",
                    "database-access-layer",
                    "orm-migration",
                    "service-layer",
                    "utility-helper",
                    "shared-constants-enums",
                    "type-definitions",
                    "configuration",
                    "environment-setup",
                    "entrypoint-main",
                    "cli-command",
                    "factory-provider",
                    "event-handler-listener",
                    "message-queue-worker",
                    "cron-scheduled-task",
                    "state-management-store",
                    "ui-component",
                    "ui-page-view",
                    "ui-layout-template",
                    "ui-hook-composable",
                    "ui-context-provider",
                    "ui-style-theme",
                    "test-unit",
                    "test-integration",
                    "test-e2e",
                    "test-fixture-factory",
                    "test-helper-utility",
                    "mock-stub",
                    "documentation-generator",
                    "build-script",
                    "deployment-infra",
                    "logging-telemetry",
                    "error-handling-boundary",
                    "serialization-parsing",
                    "validation-sanitization",
                    "caching-layer",
                    "adapter-wrapper",
                    "plugin-extension",
                    "index-barrel-reexport",
                    "generated-code",
                    "seed-data-fixture",
                    "internationalization-i18n",
                    "feature-flag-gate",
                ],
            },
        }
        return await self.decide(state, questions)

    async def score_semantic_risk(
        self,
        file_path: str,
        language: str,
        loc: int,
        complexity: int,
        fan_in: int,
        fan_out: int,
        churn_count: int,
        symbols: list[str],
        imports: list[str],
        dependents: list[str],
        external_deps: list[str],
        summary: str = "",
        deterministic_score: float = 0.0,
    ) -> JevResult | None:
        """Bond 2: Score the semantic refactoring risk of a file."""
        state = {
            "file_path": file_path,
            "language": language,
            "loc": loc,
            "complexity": complexity,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "churn_count": churn_count,
            "symbols": symbols[:30],
            "imports": imports[:20],
            "dependents": dependents[:20],
            "external_deps": external_deps[:20],
            "ai_summary": summary,
            "current_deterministic_risk_score": deterministic_score,
        }
        questions = {
            "semantic_risk": {
                "type": "score",
                "question": (
                    "Evaluate how risky it would be to modify, refactor, or delete this file. "
                    "Consider: (1) Is this file a critical chokepoint in the dependency graph? "
                    "(2) Does it implement security, authentication, or data-integrity logic? "
                    "(3) Is it a shared contract or schema that many other files depend on implicitly? "
                    "(4) Does it manage state that is hard to reason about? "
                    "(5) Is the complexity concentrated in fragile patterns (deep nesting, global mutation)? "
                    "(6) Does the churn suggest instability or active development that compounds risk? "
                    "A score of 1 means trivially safe to touch; 10 means extremely dangerous."
                ),
                "scale": [1, 10],
            },
            "risk_category": {
                "type": "choice",
                "question": (
                    "What is the primary source of risk for this file?"
                ),
                "options": [
                    "structural-chokepoint",
                    "security-critical",
                    "data-integrity",
                    "shared-contract-schema",
                    "complex-state-management",
                    "high-churn-instability",
                    "cross-cutting-concern",
                    "implicit-coupling",
                    "minimal-risk",
                ],
            },
        }
        return await self.decide(state, questions)

    async def detect_test_file(
        self,
        file_path: str,
        language: str,
        symbols: list[str],
        imports: list[str],
        external_deps: list[str],
        snippet: str = "",
    ) -> JevResult | None:
        """Bond 3: Detect whether a file is a test/spec/fixture."""
        state = {
            "file_path": file_path,
            "language": language,
            "symbols": symbols[:30],
            "imports": imports[:20],
            "external_deps": external_deps[:20],
            "source_snippet": snippet[:1500],
        }
        questions = {
            "is_test": {
                "type": "noul",
                "question": (
                    "Is this file a test file, spec file, test fixture, test factory, "
                    "test helper, test configuration (e.g., conftest.py, jest.config.js, "
                    "setup.ts), mock/stub module, or any other file whose primary purpose is "
                    "to support automated testing rather than production runtime behavior? "
                    "Consider the file path, the symbols it defines, the testing frameworks "
                    "it imports (pytest, jest, mocha, vitest, playwright, cypress, unittest, "
                    "testing-library, supertest, etc.), and whether the function/class names "
                    "follow testing conventions (test_, it(), describe(), expect(), assert)."
                ),
            },
            "test_category": {
                "type": "choice",
                "question": (
                    "If this is a test-related file, what specific category does it fall into?"
                ),
                "options": [
                    "unit-test",
                    "integration-test",
                    "end-to-end-test",
                    "snapshot-test",
                    "performance-benchmark-test",
                    "test-fixture-factory",
                    "test-helper-utility",
                    "test-configuration",
                    "mock-stub-module",
                    "not-a-test-file",
                ],
            },
        }
        return await self.decide(state, questions)

    async def route_query(
        self,
        question: str,
        repo_has_summaries: bool = False,
    ) -> JevResult | None:
        """Bond 4: Classify user question intent for smart routing."""
        state = {
            "user_question": question,
            "repo_has_ai_summaries": repo_has_summaries,
        }
        questions = {
            "intent": {
                "type": "choice",
                "question": (
                    "A developer is querying an architecture analysis tool about their codebase. "
                    "Classify the intent of their question to determine the optimal processing "
                    "strategy. The system supports: direct file navigation (just look up a file), "
                    "symbol lookup (find where a function/class/variable is defined), "
                    "risk assessment (which files are most dangerous to modify), "
                    "dependency tracing (what depends on X, or what does X depend on), "
                    "architecture overview (explain the high-level structure), "
                    "refactor planning (what would break if I change X), "
                    "and general AI-assisted questions (anything requiring deeper reasoning). "
                    "Choose the most specific intent that matches."
                ),
                "options": [
                    "navigate-to-file",
                    "symbol-lookup",
                    "risk-assessment",
                    "dependency-trace-forward",
                    "dependency-trace-reverse",
                    "architecture-overview",
                    "module-boundary-analysis",
                    "refactor-impact-planning",
                    "dead-code-identification",
                    "technology-stack-query",
                    "code-pattern-search",
                    "comparison-between-files",
                    "general-ai-question",
                ],
            },
            "needs_ai_generation": {
                "type": "noul",
                "question": (
                    "Does this question require a generative AI (LLM) to produce a natural-language "
                    "explanation, or can it be fully answered with structured graph data alone "
                    "(file lists, dependency trees, risk scores, symbol tables)?"
                ),
            },
        }
        return await self.decide(state, questions)

    async def assess_cluster(
        self,
        cluster_name: str,
        file_count: int,
        avg_score: float,
        max_score: float,
        file_paths: list[str],
        internal_edges: int,
        external_edges_in: int,
        external_edges_out: int,
    ) -> JevResult | None:
        """Bond 5: Assess the quality of a directory cluster."""
        state = {
            "cluster_name": cluster_name,
            "file_count": file_count,
            "avg_risk_score": avg_score,
            "max_risk_score": max_score,
            "sample_files": file_paths[:20],
            "internal_dependency_edges": internal_edges,
            "external_incoming_edges": external_edges_in,
            "external_outgoing_edges": external_edges_out,
        }
        questions = {
            "cohesion": {
                "type": "score",
                "question": (
                    "Rate the cohesion of this module/directory cluster. "
                    "High cohesion means files within the cluster are strongly related to each other "
                    "and share a single well-defined responsibility. Low cohesion means the cluster "
                    "is a grab-bag of unrelated files. Consider the file names, the ratio of "
                    "internal-to-external edges, and the cluster name. "
                    "1 = completely incoherent, 5 = perfectly cohesive."
                ),
                "scale": [1, 5],
            },
            "coupling": {
                "type": "score",
                "question": (
                    "Rate how tightly coupled this module is to the rest of the codebase. "
                    "High coupling means many external edges crossing the cluster boundary. "
                    "Low coupling means the cluster is well-encapsulated with a narrow interface. "
                    "1 = completely decoupled, 5 = deeply entangled."
                ),
                "scale": [1, 5],
            },
            "extraction_readiness": {
                "type": "choice",
                "question": (
                    "Could this module be safely extracted into a standalone package or microservice?"
                ),
                "options": [
                    "ready-to-extract",
                    "extractable-with-minor-refactoring",
                    "extractable-with-significant-refactoring",
                    "not-extractable-too-coupled",
                    "too-small-to-warrant-extraction",
                    "already-well-bounded",
                ],
            },
        }
        return await self.decide(state, questions)

    async def evaluate_refactor_safety(
        self,
        target_path: str,
        direct_dependents: list[str],
        transitive_dependents: list[dict],
        target_risk_score: float,
        target_complexity: int,
        target_loc: int,
    ) -> JevResult | None:
        """Bond 6: Evaluate whether a file is safe to refactor."""
        state = {
            "target_file": target_path,
            "target_risk_score": target_risk_score,
            "target_complexity": target_complexity,
            "target_loc": target_loc,
            "direct_dependent_count": len(direct_dependents),
            "direct_dependents": direct_dependents[:20],
            "transitive_dependent_count": len(transitive_dependents),
            "transitive_dependents": [d.get("path", d) for d in transitive_dependents[:20]],
            "max_transitive_depth": max(
                (d.get("distance", 1) for d in transitive_dependents), default=0
            ),
        }
        questions = {
            "safe_to_refactor": {
                "type": "noul",
                "question": (
                    "Given the number of direct and transitive dependents, the risk score, "
                    "the complexity, and the dependency depth — is it safe to refactor this file "
                    "in a single pull request without a staged rollout, feature flag, or "
                    "coordinated multi-team effort? Consider that a file with 0 dependents is "
                    "almost always safe, while a file with 10+ transitive dependents at depth 3+ "
                    "is risky. Also factor in whether the file is likely a shared contract."
                ),
            },
            "recommended_strategy": {
                "type": "choice",
                "question": (
                    "What refactoring strategy should the developer use for this file?"
                ),
                "options": [
                    "safe-direct-refactor",
                    "refactor-with-deprecation-period",
                    "refactor-behind-feature-flag",
                    "strangler-fig-pattern",
                    "parallel-implementation-then-swap",
                    "break-into-smaller-changes",
                    "requires-team-coordination",
                    "do-not-refactor-too-risky",
                ],
            },
            "estimated_blast_radius": {
                "type": "score",
                "question": (
                    "On a scale of 1 to 10, how large is the blast radius if this refactor "
                    "introduces a bug? 1 = affects only this file, 10 = cascading failures "
                    "across the entire application."
                ),
                "scale": [1, 10],
            },
        }
        return await self.decide(state, questions)

    async def triage_for_summary(
        self,
        file_path: str,
        language: str,
        loc: int,
        complexity: int,
        fan_in: int,
        fan_out: int,
        symbols: list[str],
        snippet: str = "",
    ) -> JevResult | None:
        """Bond 7: Decide if a file is worth sending to Gemini for summarization."""
        state = {
            "file_path": file_path,
            "language": language,
            "loc": loc,
            "complexity": complexity,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "symbol_names": symbols[:20],
            "source_snippet": snippet[:1000],
        }
        questions = {
            "needs_summary": {
                "type": "noul",
                "question": (
                    "Does this file contain enough meaningful logic, architecture, or domain "
                    "knowledge to warrant spending an LLM API call to generate an AI summary? "
                    "Files that do NOT need a summary include: empty or near-empty files, "
                    "barrel/index re-export files that just re-export symbols from other modules, "
                    "auto-generated code, pure type definition files with no logic, "
                    "configuration files that are self-documenting (package.json, tsconfig.json), "
                    "CSS/style-only files, trivial constant/enum files, and files under 10 LOC "
                    "with no complex logic. Files that DO need a summary include: files with "
                    "business logic, complex algorithms, non-obvious architectural decisions, "
                    "database queries, API handlers, middleware, state management, or anything "
                    "that a new developer would benefit from understanding."
                ),
            },
            "summary_priority": {
                "type": "score",
                "question": (
                    "If this file were to be summarized, how high priority is it relative to "
                    "other files in the codebase? A high-fan-in, high-complexity service file "
                    "should be summarized before a low-complexity utility. "
                    "1 = lowest priority, 10 = should be summarized first."
                ),
                "scale": [1, 10],
            },
        }
        return await self.decide(state, questions)

    async def detect_framework(
        self,
        file_path: str,
        language: str,
        imports: list[str],
        external_deps: list[str],
        symbols: list[str],
        snippet: str = "",
    ) -> JevResult | None:
        """Bond 8: Detect the framework ecosystem a file belongs to."""
        state = {
            "file_path": file_path,
            "language": language,
            "imports": imports[:20],
            "external_deps": external_deps[:20],
            "symbols": symbols[:20],
            "source_snippet": snippet[:1500],
        }
        questions = {
            "framework": {
                "type": "choice",
                "question": (
                    "What framework or library ecosystem does this file primarily belong to? "
                    "Analyze the imports, external dependencies, file path conventions, "
                    "and source patterns to determine the dominant framework."
                ),
                "options": [
                    "react",
                    "react-native",
                    "nextjs",
                    "remix",
                    "gatsby",
                    "vue",
                    "nuxt",
                    "angular",
                    "svelte",
                    "sveltekit",
                    "solid",
                    "astro",
                    "express",
                    "fastify",
                    "nestjs",
                    "koa",
                    "hono",
                    "fastapi",
                    "flask",
                    "django",
                    "starlette",
                    "litestar",
                    "tornado",
                    "aiohttp",
                    "celery",
                    "sqlalchemy",
                    "prisma",
                    "drizzle",
                    "typeorm",
                    "sequelize",
                    "mongoose",
                    "pydantic",
                    "pytest",
                    "jest",
                    "vitest",
                    "mocha",
                    "playwright",
                    "cypress",
                    "storybook",
                    "tailwindcss",
                    "electron",
                    "tauri",
                    "generic-python",
                    "generic-javascript",
                    "generic-typescript",
                    "framework-agnostic",
                    "unknown",
                ],
            },
            "layer": {
                "type": "choice",
                "question": (
                    "In a standard layered architecture, which layer does this file belong to?"
                ),
                "options": [
                    "presentation-ui",
                    "api-transport",
                    "application-service",
                    "domain-business",
                    "infrastructure-persistence",
                    "infrastructure-messaging",
                    "infrastructure-external-service",
                    "cross-cutting-concern",
                    "build-tooling",
                    "testing",
                    "configuration",
                    "unknown",
                ],
            },
        }
        return await self.decide(state, questions)

    async def should_resummarize(
        self,
        file_path: str,
        language: str,
        old_loc: int,
        new_loc: int,
        old_complexity: int,
        new_complexity: int,
        old_content_hash: str,
        new_content_hash: str,
        existing_summary: str,
    ) -> JevResult | None:
        """Bond 9: Decide if a changed file needs re-summarization."""
        state = {
            "file_path": file_path,
            "language": language,
            "previous_loc": old_loc,
            "current_loc": new_loc,
            "loc_delta": new_loc - old_loc,
            "loc_delta_percent": round(
                abs(new_loc - old_loc) / max(old_loc, 1) * 100, 1
            ),
            "previous_complexity": old_complexity,
            "current_complexity": new_complexity,
            "complexity_delta": new_complexity - old_complexity,
            "content_hash_changed": old_content_hash != new_content_hash,
            "existing_summary_preview": existing_summary[:500],
        }
        questions = {
            "needs_resummarize": {
                "type": "noul",
                "question": (
                    "A file in the codebase has been modified since its last AI summary was "
                    "generated. Based on the magnitude of changes (LOC delta, complexity delta), "
                    "is the existing summary likely to be materially invalidated? "
                    "Changes that should NOT trigger re-summarization include: "
                    "whitespace-only changes, comment additions/edits, import reordering, "
                    "formatting changes, renaming of local variables, and minor constant tweaks. "
                    "Changes that SHOULD trigger re-summarization include: "
                    "new function/class definitions, changed function signatures, "
                    "new dependencies added, significant logic changes (complexity delta > 3), "
                    "LOC change > 20%, and structural refactors."
                ),
            },
            "change_significance": {
                "type": "score",
                "question": (
                    "How significant is this change to the file's architectural role? "
                    "1 = cosmetic/trivial, 10 = fundamental structural change."
                ),
                "scale": [1, 10],
            },
        }
        return await self.decide(state, questions)

    async def detect_dead_code(
        self,
        file_path: str,
        language: str,
        loc: int,
        fan_in: int,
        fan_out: int,
        churn_count: int,
        last_modified: str | None,
        symbols: list[str],
        external_deps: list[str],
        snippet: str = "",
    ) -> JevResult | None:
        """Bond 10: Detect whether a file is likely dead/unused code."""
        state = {
            "file_path": file_path,
            "language": language,
            "loc": loc,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "churn_count": churn_count,
            "last_modified": last_modified or "unknown",
            "symbols": symbols[:20],
            "external_deps": external_deps[:20],
            "source_snippet": snippet[:1000],
        }
        questions = {
            "is_dead_code": {
                "type": "noul",
                "question": (
                    "Is this file likely dead code — meaning it is no longer used by any "
                    "other file in the codebase, is not an entrypoint, is not a CLI script, "
                    "is not dynamically loaded, and serves no active purpose? "
                    "Consider: zero fan-in strongly suggests dead code UNLESS the file is an "
                    "entrypoint (main.py, index.ts, app startup), a CLI command, a cron job, "
                    "a migration script, a standalone utility meant to be run directly, "
                    "or a plugin that is loaded dynamically by convention. "
                    "Low churn (no edits recently) combined with zero fan-in is a strong signal. "
                    "Also consider whether the file path suggests it was deprecated or replaced "
                    "(e.g., old_, deprecated_, backup_, .bak)."
                ),
            },
            "dead_code_category": {
                "type": "choice",
                "question": (
                    "If the file appears to be dead code, what category does it fall into?"
                ),
                "options": [
                    "abandoned-feature",
                    "replaced-by-newer-implementation",
                    "leftover-from-refactor",
                    "deprecated-api-version",
                    "experimental-prototype",
                    "unused-utility",
                    "orphaned-test",
                    "stale-migration-seed",
                    "backup-copy",
                    "not-dead-code",
                ],
            },
        }
        return await self.decide(state, questions)


# Module-level singleton
jev_client = JevClient()
