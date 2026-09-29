"""
TypeSafe Jev decision client for Codebase Cartographer.

Provides typed wrappers around Jev's three primitives (Choice, Noul, Score)
for all 10 integration bonds. Falls back gracefully when Jev is unavailable.
"""

import logging
from typing import Any

import httpx
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score

from app.core.config import settings

logger = logging.getLogger(__name__)


class JevDecision:
    """Parsed result from a single Jev question."""
    def __init__(self, raw: dict):
        self.answer = raw.get("choice", raw.get("answer"))            # For Choice
        self.probability = raw.get("noul", raw.get("probability"))  # For Noul
        self.value = raw.get("score", raw.get("value"))              # For Score
        self.confidence = raw.get("confidence", 0.0)
        self.distribution = raw.get("probabilities", raw.get("distribution", {}))  # Full prob per option

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
        self.api_key = settings.typesafe_api_key
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



        try:
            ts_client = AsyncTypeSafeClient(api_key=self.api_key, base_url=self.base_url)
            # Remove any raw types if they were somehow passed as dicts
            response = await ts_client.system_one(
                state=state,
                questions=questions,
                timeout=timeout
            )
        except Exception as exc:
            logger.warning("Jev API request failed: %s", exc)
            return None

        decisions = {
            name: JevDecision(ans.model_dump()) for name, ans in response.answers.items()
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
            "architectural_role": Choice(
                instructions= (
                    "Analyze this source file's structural metadata and source snippet. "
                    "What is the primary architectural role this file plays in the codebase? "
                    "Consider the file path, the symbols it defines, its import/export patterns, "
                    "its complexity, and its position in the dependency graph (fan-in/fan-out)."
                ),
                criteria={
                    "core-business-logic": "core-business-logic",
                    "api-endpoint-handler": "api-endpoint-handler",
                    "api-route-definition": "api-route-definition",
                    "middleware": "middleware",
                    "authentication-authorization": "authentication-authorization",
                    "data-model-schema": "data-model-schema",
                    "database-access-layer": "database-access-layer",
                    "orm-migration": "orm-migration",
                    "service-layer": "service-layer",
                    "utility-helper": "utility-helper",
                    "shared-constants-enums": "shared-constants-enums",
                    "type-definitions": "type-definitions",
                    "configuration": "configuration",
                    "environment-setup": "environment-setup",
                    "entrypoint-main": "entrypoint-main",
                    "cli-command": "cli-command",
                    "factory-provider": "factory-provider",
                    "event-handler-listener": "event-handler-listener",
                    "message-queue-worker": "message-queue-worker",
                    "cron-scheduled-task": "cron-scheduled-task",
                    "state-management-store": "state-management-store",
                    "ui-component": "ui-component",
                    "ui-page-view": "ui-page-view",
                    "ui-layout-template": "ui-layout-template",
                    "ui-hook-composable": "ui-hook-composable",
                    "ui-context-provider": "ui-context-provider",
                    "ui-style-theme": "ui-style-theme",
                    "test-unit": "test-unit",
                    "test-integration": "test-integration",
                    "test-e2e": "test-e2e",
                    "test-fixture-factory": "test-fixture-factory",
                    "test-helper-utility": "test-helper-utility",
                    "mock-stub": "mock-stub",
                    "documentation-generator": "documentation-generator",
                    "build-script": "build-script",
                    "deployment-infra": "deployment-infra",
                    "logging-telemetry": "logging-telemetry",
                    "error-handling-boundary": "error-handling-boundary",
                    "serialization-parsing": "serialization-parsing",
                    "validation-sanitization": "validation-sanitization",
                    "caching-layer": "caching-layer",
                    "adapter-wrapper": "adapter-wrapper",
                    "plugin-extension": "plugin-extension",
                    "index-barrel-reexport": "index-barrel-reexport",
                    "generated-code": "generated-code",
                    "seed-data-fixture": "seed-data-fixture",
                    "internationalization-i18n": "internationalization-i18n",
                    "feature-flag-gate": "feature-flag-gate",
                },
            ),
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
            "semantic_risk": Score(
                instructions= (
                    "Evaluate how risky it would be to modify, refactor, or delete this file. "
                    "Consider: (1) Is this file a critical chokepoint in the dependency graph? "
                    "(2) Does it implement security, authentication, or data-integrity logic? "
                    "(3) Is it a shared contract or schema that many other files depend on implicitly? "
                    "(4) Does it manage state that is hard to reason about? "
                    "(5) Is the complexity concentrated in fragile patterns (deep nesting, global mutation)? "
                    "(6) Does the churn suggest instability or active development that compounds risk? "
                    "A score of 1 means trivially safe to touch; 10 means extremely dangerous."
                ),
                criteria=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            ),
            "risk_category": Choice(
                instructions= (
                    "What is the primary source of risk for this file?"
                ),
                criteria={
                    "structural-chokepoint": "structural-chokepoint",
                    "security-critical": "security-critical",
                    "data-integrity": "data-integrity",
                    "shared-contract-schema": "shared-contract-schema",
                    "complex-state-management": "complex-state-management",
                    "high-churn-instability": "high-churn-instability",
                    "cross-cutting-concern": "cross-cutting-concern",
                    "implicit-coupling": "implicit-coupling",
                    "minimal-risk": "minimal-risk",
                },
            ),
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
            "is_test": Noul(
                instructions= (
                    "Is this file a test file, spec file, test fixture, test factory, "
                    "test helper, test configuration (e.g., conftest.py, jest.config.js, "
                    "setup.ts), mock/stub module, or any other file whose primary purpose is "
                    "to support automated testing rather than production runtime behavior? "
                    "Consider the file path, the symbols it defines, the testing frameworks "
                    "it imports (pytest, jest, mocha, vitest, playwright, cypress, unittest, "
                    "testing-library, supertest, etc.), and whether the function/class names "
                    "follow testing conventions (test_, it(), describe(), expect(), assert)."
                ),
            ),
            "test_category": Choice(
                instructions= (
                    "If this is a test-related file, what specific category does it fall into?"
                ),
                criteria={
                    "unit-test": "unit-test",
                    "integration-test": "integration-test",
                    "end-to-end-test": "end-to-end-test",
                    "snapshot-test": "snapshot-test",
                    "performance-benchmark-test": "performance-benchmark-test",
                    "test-fixture-factory": "test-fixture-factory",
                    "test-helper-utility": "test-helper-utility",
                    "test-configuration": "test-configuration",
                    "mock-stub-module": "mock-stub-module",
                    "not-a-test-file": "not-a-test-file",
                },
            ),
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
            "intent": Choice(
                instructions= (
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
                criteria={
                    "navigate-to-file": "navigate-to-file",
                    "symbol-lookup": "symbol-lookup",
                    "risk-assessment": "risk-assessment",
                    "dependency-trace-forward": "dependency-trace-forward",
                    "dependency-trace-reverse": "dependency-trace-reverse",
                    "architecture-overview": "architecture-overview",
                    "module-boundary-analysis": "module-boundary-analysis",
                    "refactor-impact-planning": "refactor-impact-planning",
                    "dead-code-identification": "dead-code-identification",
                    "technology-stack-query": "technology-stack-query",
                    "code-pattern-search": "code-pattern-search",
                    "comparison-between-files": "comparison-between-files",
                    "general-ai-question": "general-ai-question",
                },
            ),
            "needs_ai_generation": Noul(
                instructions= (
                    "Does this question require a generative AI (LLM) to produce a natural-language "
                    "explanation, or can it be fully answered with structured graph data alone "
                    "(file lists, dependency trees, risk scores, symbol tables)?"
                ),
            ),
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
            "cohesion": Score(
                instructions= (
                    "Rate the cohesion of this module/directory cluster. "
                    "High cohesion means files within the cluster are strongly related to each other "
                    "and share a single well-defined responsibility. Low cohesion means the cluster "
                    "is a grab-bag of unrelated files. Consider the file names, the ratio of "
                    "internal-to-external edges, and the cluster name. "
                    "1 = completely incoherent, 5 = perfectly cohesive."
                ),
                criteria=["1", "2", "3", "4", "5"],
            ),
            "coupling": Score(
                instructions= (
                    "Rate how tightly coupled this module is to the rest of the codebase. "
                    "High coupling means many external edges crossing the cluster boundary. "
                    "Low coupling means the cluster is well-encapsulated with a narrow interface. "
                    "1 = completely decoupled, 5 = deeply entangled."
                ),
                criteria=["1", "2", "3", "4", "5"],
            ),
            "extraction_readiness": Choice(
                instructions= (
                    "Could this module be safely extracted into a standalone package or microservice?"
                ),
                criteria={
                    "ready-to-extract": "ready-to-extract",
                    "extractable-with-minor-refactoring": "extractable-with-minor-refactoring",
                    "extractable-with-significant-refactoring": "extractable-with-significant-refactoring",
                    "not-extractable-too-coupled": "not-extractable-too-coupled",
                    "too-small-to-warrant-extraction": "too-small-to-warrant-extraction",
                    "already-well-bounded": "already-well-bounded",
                },
            ),
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
            "safe_to_refactor": Noul(
                instructions= (
                    "Given the number of direct and transitive dependents, the risk score, "
                    "the complexity, and the dependency depth — is it safe to refactor this file "
                    "in a single pull request without a staged rollout, feature flag, or "
                    "coordinated multi-team effort? Consider that a file with 0 dependents is "
                    "almost always safe, while a file with 10+ transitive dependents at depth 3+ "
                    "is risky. Also factor in whether the file is likely a shared contract."
                ),
            ),
            "recommended_strategy": Choice(
                instructions= (
                    "What refactoring strategy should the developer use for this file?"
                ),
                criteria={
                    "safe-direct-refactor": "safe-direct-refactor",
                    "refactor-with-deprecation-period": "refactor-with-deprecation-period",
                    "refactor-behind-feature-flag": "refactor-behind-feature-flag",
                    "strangler-fig-pattern": "strangler-fig-pattern",
                    "parallel-implementation-then-swap": "parallel-implementation-then-swap",
                    "break-into-smaller-changes": "break-into-smaller-changes",
                    "requires-team-coordination": "requires-team-coordination",
                    "do-not-refactor-too-risky": "do-not-refactor-too-risky",
                },
            ),
            "estimated_blast_radius": Score(
                instructions= (
                    "On a scale of 1 to 10, how large is the blast radius if this refactor "
                    "introduces a bug? 1 = affects only this file, 10 = cascading failures "
                    "across the entire application."
                ),
                criteria=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            ),
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
            "needs_summary": Noul(
                instructions= (
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
            ),
            "summary_priority": Score(
                instructions= (
                    "If this file were to be summarized, how high priority is it relative to "
                    "other files in the codebase? A high-fan-in, high-complexity service file "
                    "should be summarized before a low-complexity utility. "
                    "1 = lowest priority, 10 = should be summarized first."
                ),
                criteria=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            ),
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
            "framework": Choice(
                instructions= (
                    "What framework or library ecosystem does this file primarily belong to? "
                    "Analyze the imports, external dependencies, file path conventions, "
                    "and source patterns to determine the dominant framework."
                ),
                criteria={
                    "react": "react",
                    "react-native": "react-native",
                    "nextjs": "nextjs",
                    "remix": "remix",
                    "gatsby": "gatsby",
                    "vue": "vue",
                    "nuxt": "nuxt",
                    "angular": "angular",
                    "svelte": "svelte",
                    "sveltekit": "sveltekit",
                    "solid": "solid",
                    "astro": "astro",
                    "express": "express",
                    "fastify": "fastify",
                    "nestjs": "nestjs",
                    "koa": "koa",
                    "hono": "hono",
                    "fastapi": "fastapi",
                    "flask": "flask",
                    "django": "django",
                    "starlette": "starlette",
                    "litestar": "litestar",
                    "tornado": "tornado",
                    "aiohttp": "aiohttp",
                    "celery": "celery",
                    "sqlalchemy": "sqlalchemy",
                    "prisma": "prisma",
                    "drizzle": "drizzle",
                    "typeorm": "typeorm",
                    "sequelize": "sequelize",
                    "mongoose": "mongoose",
                    "pydantic": "pydantic",
                    "pytest": "pytest",
                    "jest": "jest",
                    "vitest": "vitest",
                    "mocha": "mocha",
                    "playwright": "playwright",
                    "cypress": "cypress",
                    "storybook": "storybook",
                    "tailwindcss": "tailwindcss",
                    "electron": "electron",
                    "tauri": "tauri",
                    "generic-python": "generic-python",
                    "generic-javascript": "generic-javascript",
                    "generic-typescript": "generic-typescript",
                    "framework-agnostic": "framework-agnostic",
                    "unknown": "unknown",
                },
            ),
            "layer": Choice(
                instructions= (
                    "In a standard layered architecture, which layer does this file belong to?"
                ),
                criteria={
                    "presentation-ui": "presentation-ui",
                    "api-transport": "api-transport",
                    "application-service": "application-service",
                    "domain-business": "domain-business",
                    "infrastructure-persistence": "infrastructure-persistence",
                    "infrastructure-messaging": "infrastructure-messaging",
                    "infrastructure-external-service": "infrastructure-external-service",
                    "cross-cutting-concern": "cross-cutting-concern",
                    "build-tooling": "build-tooling",
                    "testing": "testing",
                    "configuration": "configuration",
                    "unknown": "unknown",
                },
            ),
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
            "needs_resummarize": Noul(
                instructions= (
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
            ),
            "change_significance": Score(
                instructions= (
                    "How significant is this change to the file's architectural role? "
                    "1 = cosmetic/trivial, 10 = fundamental structural change."
                ),
                criteria=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            ),
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
            "is_dead_code": Noul(
                instructions= (
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
            ),
            "dead_code_category": Choice(
                instructions= (
                    "If the file appears to be dead code, what category does it fall into?"
                ),
                criteria={
                    "abandoned-feature": "abandoned-feature",
                    "replaced-by-newer-implementation": "replaced-by-newer-implementation",
                    "leftover-from-refactor": "leftover-from-refactor",
                    "deprecated-api-version": "deprecated-api-version",
                    "experimental-prototype": "experimental-prototype",
                    "unused-utility": "unused-utility",
                    "orphaned-test": "orphaned-test",
                    "stale-migration-seed": "stale-migration-seed",
                    "backup-copy": "backup-copy",
                    "not-dead-code": "not-dead-code",
                },
            ),
        }
        return await self.decide(state, questions)


# Module-level singleton
jev_client = JevClient()
