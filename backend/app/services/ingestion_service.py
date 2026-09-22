"""Ingestion and Analysis Pipeline Service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.domain.enums import FindingCategory, FindingSeverity, JobStatus
from app.infrastructure.db.models.analysis_job import AnalysisJob
from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.infrastructure.db.models.defect_prediction import DefectPrediction
from app.infrastructure.db.models.file_metric import FileMetric
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.db.models.repository import Repository
from app.infrastructure.db.models.review_comment import ReviewComment
from app.infrastructure.git.cloner import GitCloner
from app.infrastructure.git.dependency_graph import DependencyGraphBuilder
from app.infrastructure.git.detector import LanguageDetector
from app.infrastructure.git.indexer import FileIndexer
from app.infrastructure.redis.pubsub import EventBroadcaster
from app.infrastructure.static_analysis.engine import StaticAnalysisEngine
from app.services.hybrid_review_service import hybrid_review_service
from app.services.ml_service import ml_defect_service
from app.services.scoring_service import QualityScorecard, ScoringService


@dataclass
class JobStageUpdate:
    """Encapsulates job progress state updates."""

    status: JobStatus
    stage: str
    progress: float
    message: str
    error_message: str | None = None


@dataclass
class ProjectMetadata:
    """Project-level language and structural metadata."""

    primary_lang: str
    lang_counts: dict[str, int]
    project_types: list[str]


@dataclass
class PipelineArtifacts:
    """Aggregated analysis artifacts produced across AST and ML stages."""

    file_metrics: list[FileMetric]
    issues: list[Issue]
    defect_predictions: list[DefectPrediction]
    total_sloc: int
    total_functions: int
    total_classes: int


@dataclass
class ReportPersistenceContext:
    """Context container for scorecard computation and report database persistence."""

    job: AnalysisJob
    repo: Repository
    artifacts: PipelineArtifacts
    metadata: ProjectMetadata
    dep_graph: Any
    review_comments: list[ReviewComment]


def _execute_static_analysis(
    clone_path: Path,
    indexed_files: list[Path],
    arch_issues: list[Issue],
) -> PipelineArtifacts:
    """Runs AST visitors and defect predictions across source files."""
    file_metrics: list[FileMetric] = []
    issues: list[Issue] = list(arch_issues)
    defect_predictions: list[DefectPrediction] = []
    sloc = 0
    fn_count = 0
    cls_count = 0

    for f_path in indexed_files:
        rel_path = str(f_path.relative_to(clone_path)).replace("\\", "/")
        try:
            content = f_path.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue

        if f_path.suffix == ".py":
            result = StaticAnalysisEngine.analyze_python_file(rel_path, content)
            file_metrics.append(result.metric)
            issues.extend(result.issues)

            sloc += result.metric.sloc
            fn_count += result.metric.function_count
            cls_count += result.metric.class_count

            pred = ml_defect_service.predict_file(result.metric, report_id="")
            defect_predictions.append(pred)

    return PipelineArtifacts(
        file_metrics=file_metrics,
        issues=issues,
        defect_predictions=defect_predictions,
        total_sloc=sloc,
        total_functions=fn_count,
        total_classes=cls_count,
    )


async def _execute_ai_reviews(
    repo_id: str,
    clone_path: Path,
    target_files: list[Path],
    artifacts: PipelineArtifacts,
) -> list[ReviewComment]:
    """Runs hybrid AI reviews on targeted files."""
    review_comments: list[ReviewComment] = []
    for f_path in target_files:
        rel_path = str(f_path.relative_to(clone_path)).replace("\\", "/")
        try:
            content = f_path.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        file_issues = [iss for iss in artifacts.issues if iss.file_path == rel_path]
        file_dp = next(
            (dp for dp in artifacts.defect_predictions if dp.file_path == rel_path), None
        )
        comments, _ = await hybrid_review_service.review_file(
            repository_id=repo_id,
            file_path=rel_path,
            code_content=content,
            static_issues=file_issues,
            defect_prediction=file_dp,
            report_id="",
        )
        review_comments.extend(comments)
    return review_comments


def _create_report_record(
    ctx: ReportPersistenceContext,
    scorecard: QualityScorecard,
) -> AnalysisReport:
    """Builds the AnalysisReport database entity."""
    return AnalysisReport(
        job_id=ctx.job.id,
        overall_score=scorecard.overall_score,
        maintainability_score=scorecard.maintainability_score,
        security_score=scorecard.security_score,
        testing_score=scorecard.testing_score,
        architecture_score=scorecard.architecture_score,
        total_files=len(ctx.artifacts.file_metrics),
        total_lines_of_code=ctx.artifacts.total_sloc,
        total_functions=ctx.artifacts.total_functions,
        total_classes=ctx.artifacts.total_classes,
        technical_debt_minutes=scorecard.technical_debt_minutes,
        summary_metadata={
            "primary_language": ctx.metadata.primary_lang,
            "languages": ctx.metadata.lang_counts,
            "project_types": ctx.metadata.project_types,
            "circular_dependencies_count": len(ctx.dep_graph.circular_dependencies),
            "total_modules": len(ctx.dep_graph.nodes),
        },
    )


class IngestionService:
    """Coordinates the ingestion, AST parsing, defect scoring, and review generation pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cloner = GitCloner()

    async def run_pipeline(self, job_id: str) -> AnalysisReport:
        """Executes the complete analysis pipeline for a job."""
        job = await self.session.get(AnalysisJob, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        repo = await self.session.get(Repository, job.repository_id)
        if not repo:
            raise ValueError(f"Repository {job.repository_id} not found")

        clone_path: Path | None = None
        is_local_dir = False

        try:
            clone_path, is_local_dir = await self._run_cloning_stage(job, repo)
            indexed_files, py_files, meta = await self._run_indexing_stage(job, repo, clone_path)
            dep_graph, arch_issues = await self._run_dependency_stage(job, clone_path, py_files)
            artifacts = await self._run_static_analysis_stage(
                job, clone_path, indexed_files, arch_issues
            )
            review_comments = await self._run_ai_review_stage(
                job, repo.id, clone_path, artifacts
            )

            ctx = ReportPersistenceContext(
                job=job,
                repo=repo,
                artifacts=artifacts,
                metadata=meta,
                dep_graph=dep_graph,
                review_comments=review_comments,
            )
            return await self._persist_report_stage(ctx)

        except Exception as e:
            logger.exception(f"Pipeline failure for job {job_id}: {e}")
            await self._update_job(
                job,
                JobStageUpdate(
                    status=JobStatus.FAILED,
                    stage="FAILED",
                    progress=100.0,
                    message=f"Error: {str(e)}",
                    error_message=str(e),
                ),
            )
            raise
        finally:
            if clone_path and not is_local_dir:
                self.cloner.cleanup(clone_path)

    async def _run_cloning_stage(
        self, job: AnalysisJob, repo: Repository
    ) -> tuple[Path, bool]:
        """Resolves target source code path via local directory or git clone."""
        await self._update_job(
            job,
            JobStageUpdate(
                status=JobStatus.CLONING,
                stage="CLONING",
                progress=15.0,
                message="Cloning or loading repository...",
            ),
        )

        url = repo.url.strip()
        if url.startswith("file://"):
            local_candidate = Path(url[7:])
            if local_candidate.exists() and local_candidate.is_dir():
                return local_candidate, True
        elif Path(url).exists() and Path(url).is_dir():
            return Path(url), True

        clone_path = self.cloner.clone_repository(repo.url, branch=job.branch)
        return clone_path, False

    async def _run_indexing_stage(
        self, job: AnalysisJob, repo: Repository, clone_path: Path
    ) -> tuple[list[Path], list[Path], ProjectMetadata]:
        """Indexes repository files and discovers language composition."""
        await self._update_job(
            job,
            JobStageUpdate(
                status=JobStatus.INDEXING,
                stage="INDEXING",
                progress=35.0,
                message="Indexing files and detecting project structure...",
            ),
        )
        primary_lang, lang_counts = LanguageDetector.detect_languages(clone_path)
        project_types = LanguageDetector.detect_project_type(clone_path)
        repo.primary_language = primary_lang
        repo.languages = lang_counts
        repo.disk_size_bytes = sum(
            f.stat().st_size for f in clone_path.glob("**/*") if f.is_file()
        )

        indexed_files = FileIndexer.index_all(clone_path)
        py_files = [f for f in indexed_files if f.suffix == ".py"]
        metadata = ProjectMetadata(
            primary_lang=primary_lang,
            lang_counts=lang_counts,
            project_types=project_types,
        )
        return indexed_files, py_files, metadata

    async def _run_dependency_stage(
        self, job: AnalysisJob, clone_path: Path, py_files: list[Path]
    ) -> tuple[Any, list[Issue]]:
        """Constructs module dependency graph and detects circular dependencies."""
        await self._update_job(
            job,
            JobStageUpdate(
                status=JobStatus.STATIC_ANALYSIS,
                stage="DEPENDENCY_ANALYSIS",
                progress=50.0,
                message="Analyzing dependency graph and architecture...",
            ),
        )
        dep_graph = DependencyGraphBuilder.build_graph(clone_path, py_files)
        arch_issues: list[Issue] = []

        for cycle in dep_graph.circular_dependencies:
            root_mod = cycle.cycle_path[0]
            arch_issues.append(
                Issue(
                    report_id="",
                    rule_id="ARCH-CIRCULAR-DEPENDENCY",
                    category=FindingCategory.ARCHITECTURE,
                    severity=FindingSeverity.HIGH,
                    file_path=f"{root_mod.replace('.', '/')}.py",
                    line_start=1,
                    line_end=1,
                    title=f"Circular Dependency in {len(cycle.cycle_path) - 1} Modules",
                    description=cycle.description,
                    snippet=" -> ".join(cycle.cycle_path),
                    remediation="Decouple mutually dependent modules using interfaces or dependency injection.",
                    cwe_id="CWE-1047",
                )
            )
        return dep_graph, arch_issues

    async def _run_static_analysis_stage(
        self,
        job: AnalysisJob,
        clone_path: Path,
        indexed_files: list[Path],
        arch_issues: list[Issue],
    ) -> PipelineArtifacts:
        """Runs AST visitors and defect predictions across source files."""
        await self._update_job(
            job,
            JobStageUpdate(
                status=JobStatus.STATIC_ANALYSIS,
                stage="STATIC_ANALYSIS",
                progress=70.0,
                message="Parsing AST and computing metrics...",
            ),
        )
        return _execute_static_analysis(clone_path, indexed_files, arch_issues)

    async def _run_ai_review_stage(
        self,
        job: AnalysisJob,
        repo_id: str,
        clone_path: Path,
        artifacts: PipelineArtifacts,
    ) -> list[ReviewComment]:
        """Synthesizes AI code reviews via hybrid static and ML triangulation."""
        await self._update_job(
            job,
            JobStageUpdate(
                status=JobStatus.AI_REVIEW,
                stage="AI_REVIEW",
                progress=75.0,
                message="Synthesizing AI code reviews...",
            ),
        )
        issue_files = {iss.file_path for iss in artifacts.issues}
        high_risk_files = {
            dp.file_path for dp in artifacts.defect_predictions if dp.defect_probability >= 0.35
        }
        targets = self._select_review_targets(clone_path, artifacts.file_metrics, issue_files, high_risk_files)
        return await _execute_ai_reviews(repo_id, clone_path, targets, artifacts)

    @staticmethod
    def _select_review_targets(
        clone_path: Path,
        file_metrics: list[FileMetric],
        issue_files: set[str],
        high_risk_files: set[str],
    ) -> list[Path]:
        """Prioritizes files with detected defects or security issues for AI review."""
        priority_files: list[Path] = []
        code_files: list[Path] = []

        for m in file_metrics:
            rel = m.file_path.replace("\\", "/")
            p = clone_path / rel
            if not p.exists():
                continue
            if rel in issue_files or rel in high_risk_files:
                priority_files.append(p)
            else:
                code_files.append(p)

        return (priority_files + code_files)[:25]

    async def _persist_report_stage(self, ctx: ReportPersistenceContext) -> AnalysisReport:
        """Calculates multi-dimensional scorecard and persists analysis results."""
        await self._update_job(
            ctx.job,
            JobStageUpdate(
                status=JobStatus.AGGREGATING,
                stage="AGGREGATING",
                progress=90.0,
                message="Synthesizing quality scorecard...",
            ),
        )
        circular_cycles = [c.cycle_path for c in ctx.dep_graph.circular_dependencies]
        scorecard = ScoringService.calculate_scores(
            file_metrics=ctx.artifacts.file_metrics,
            issues=ctx.artifacts.issues,
            circular_dependencies=circular_cycles,
            defect_predictions=ctx.artifacts.defect_predictions,
        )

        report = _create_report_record(ctx, scorecard)
        self.session.add(report)
        await self.session.flush()

        _bind_report_entities(self.session, report.id, ctx.artifacts, ctx.review_comments)

        await self._update_job(
            ctx.job,
            JobStageUpdate(
                status=JobStatus.COMPLETED,
                stage="COMPLETED",
                progress=100.0,
                message="Analysis complete.",
            ),
        )
        return report

def _bind_report_entities(
    session: AsyncSession,
    report_id: str,
    artifacts: PipelineArtifacts,
    review_comments: list[ReviewComment],
) -> None:
    """Attaches report ID foreign key to all child metrics and findings."""
    for m in artifacts.file_metrics:
        m.report_id = report_id
        session.add(m)
    for i in artifacts.issues:
        i.report_id = report_id
        session.add(i)
    for dp in artifacts.defect_predictions:
        dp.report_id = report_id
        session.add(dp)
    for rc in review_comments:
        rc.report_id = report_id
        session.add(rc)

    async def _update_job(self, job: AnalysisJob, update: JobStageUpdate) -> None:
        """Updates analysis job progress and publishes WebSocket notification."""
        job.status = update.status
        job.current_stage = update.stage
        job.progress_percent = update.progress
        if update.error_message:
            job.error_message = update.error_message
        await self.session.commit()
        await EventBroadcaster.publish_event(
            job.id, update.stage, update.progress, update.message
        )
