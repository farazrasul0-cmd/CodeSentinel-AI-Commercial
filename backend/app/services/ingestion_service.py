"""Ingestion and Analysis Pipeline Service."""

from pathlib import Path

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
from app.services.scoring_service import ScoringService


class IngestionService:
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
            # 1. INGESTION (Local path or Remote Git Clone)
            await self._update_job(
                job, JobStatus.CLONING, "CLONING", 15.0, "Cloning or loading repository..."
            )

            url = repo.url.strip()
            if url.startswith("file://"):
                local_candidate = Path(url[7:])
                if local_candidate.exists() and local_candidate.is_dir():
                    clone_path = local_candidate
                    is_local_dir = True
            elif Path(url).exists() and Path(url).is_dir():
                clone_path = Path(url)
                is_local_dir = True

            if not clone_path:
                clone_path = self.cloner.clone_repository(repo.url, branch=job.branch)

            # 2. LANGUAGE DETECTION & INDEXING
            await self._update_job(
                job,
                JobStatus.INDEXING,
                "INDEXING",
                35.0,
                "Indexing files and detecting project structure...",
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

            # 3. DEPENDENCY GRAPH & ARCHITECTURE ANALYSIS
            await self._update_job(
                job,
                JobStatus.STATIC_ANALYSIS,
                "DEPENDENCY_ANALYSIS",
                50.0,
                "Analyzing dependency graph and architecture...",
            )
            dep_graph = DependencyGraphBuilder.build_graph(clone_path, py_files)

            file_metrics: list[FileMetric] = []
            issues: list[Issue] = []
            defect_predictions: list[DefectPrediction] = []

            # Flag circular dependency violations
            for cycle in dep_graph.circular_dependencies:
                root_module = cycle.cycle_path[0]
                issues.append(
                    Issue(
                        report_id="",
                        rule_id="ARCH-CIRCULAR-DEPENDENCY",
                        category=FindingCategory.ARCHITECTURE,
                        severity=FindingSeverity.HIGH,
                        file_path=f"{root_module.replace('.', '/')}.py",
                        line_start=1,
                        line_end=1,
                        title=f"Circular Dependency in {len(cycle.cycle_path) - 1} Modules",
                        description=cycle.description,
                        snippet=" -> ".join(cycle.cycle_path),
                        remediation="Decouple mutually dependent modules using interfaces, dependency injection, or extracting shared logic.",
                        cwe_id="CWE-1047",
                    )
                )

            # 4. STATIC & AST ANALYSIS
            await self._update_job(
                job,
                JobStatus.STATIC_ANALYSIS,
                "STATIC_ANALYSIS",
                70.0,
                "Parsing AST and computing metrics...",
            )

            total_sloc = 0
            total_functions = 0
            total_classes = 0

            for f_path in indexed_files:
                rel_path = str(f_path.relative_to(clone_path)).replace("\\", "/")
                try:
                    content = f_path.read_text(encoding="utf-8-sig", errors="ignore")
                except Exception:
                    continue

                if f_path.suffix == ".py":
                    analysis_result = StaticAnalysisEngine.analyze_python_file(rel_path, content)
                    file_metrics.append(analysis_result.metric)
                    issues.extend(analysis_result.issues)

                    total_sloc += analysis_result.metric.sloc
                    total_functions += analysis_result.metric.function_count
                    total_classes += analysis_result.metric.class_count

                    # 5. DEFECT PREDICTION (ML Model + TreeSHAP Explainability)
                    prediction = ml_defect_service.predict_file(analysis_result.metric, report_id="")
                    defect_predictions.append(prediction)

            # 6. AI CODE REVIEW (Hybrid Triangulation: Static + TreeSHAP + RAG)
            await self._update_job(
                job, JobStatus.AI_REVIEW, "AI_REVIEW", 75.0, "Synthesizing AI code reviews..."
            )
            review_comments: list[ReviewComment] = []
            # Prioritize files with detected static issues or elevated defect probability
            issue_files = {iss.file_path for iss in issues}
            high_risk_files = {dp.file_path for dp in defect_predictions if dp.defect_probability >= 0.35}
            priority_files: list[Path] = []
            code_files: list[Path] = []

            for f_path in indexed_files:
                rel = str(f_path.relative_to(clone_path)).replace("\\", "/")
                if rel in issue_files or rel in high_risk_files:
                    priority_files.append(f_path)
                elif f_path.suffix in {".py", ".ts", ".js", ".tsx", ".jsx"}:
                    code_files.append(f_path)

            target_review_files = (priority_files + code_files)[:25]

            for f_path in target_review_files:
                rel_path = str(f_path.relative_to(clone_path)).replace("\\", "/")
                try:
                    content = f_path.read_text(encoding="utf-8-sig", errors="ignore")
                except Exception:
                    continue
                file_issues = [iss for iss in issues if iss.file_path == rel_path]
                file_dp = next((dp for dp in defect_predictions if dp.file_path == rel_path), None)
                comments, _ = await hybrid_review_service.review_file(
                    repository_id=repo.id,
                    file_path=rel_path,
                    code_content=content,
                    static_issues=file_issues,
                    defect_prediction=file_dp,
                    report_id="",
                )
                review_comments.extend(comments)

            # 7. AGGREGATE SCORES
            await self._update_job(
                job, JobStatus.AGGREGATING, "AGGREGATING", 90.0, "Synthesizing quality scorecard..."
            )
            scorecard = ScoringService.calculate_scores(file_metrics, issues)

            # 8. CREATE REPORT
            report = AnalysisReport(
                job_id=job.id,
                overall_score=scorecard.overall_score,
                maintainability_score=scorecard.maintainability_score,
                security_score=scorecard.security_score,
                testing_score=scorecard.testing_score,
                architecture_score=scorecard.architecture_score,
                total_files=len(file_metrics),
                total_lines_of_code=total_sloc,
                total_functions=total_functions,
                total_classes=total_classes,
                technical_debt_minutes=scorecard.technical_debt_minutes,
                summary_metadata={
                    "primary_language": primary_lang,
                    "languages": lang_counts,
                    "project_types": project_types,
                    "circular_dependencies_count": len(dep_graph.circular_dependencies),
                    "total_modules": len(dep_graph.nodes),
                },
            )
            self.session.add(report)
            await self.session.flush()

            # Bind report ID to child entities
            for m in file_metrics:
                m.report_id = report.id
                self.session.add(m)
            for i in issues:
                i.report_id = report.id
                self.session.add(i)
            for dp in defect_predictions:
                dp.report_id = report.id
                self.session.add(dp)
            for rc in review_comments:
                rc.report_id = report.id
                self.session.add(rc)

            # Mark Completed
            await self._update_job(
                job, JobStatus.COMPLETED, "COMPLETED", 100.0, "Analysis complete."
            )
            await self.session.commit()
            return report

        except Exception as e:
            logger.exception(f"Pipeline failure for job {job_id}: {e}")
            await self._update_job(
                job, JobStatus.FAILED, "FAILED", 100.0, f"Error: {str(e)}", error_message=str(e)
            )
            await self.session.commit()
            raise
        finally:
            if clone_path and not is_local_dir:
                self.cloner.cleanup(clone_path)

    async def _update_job(
        self,
        job: AnalysisJob,
        status: JobStatus,
        stage: str,
        progress: float,
        message: str,
        error_message: str | None = None,
    ) -> None:
        job.status = status
        job.current_stage = stage
        job.progress_percent = progress
        if error_message:
            job.error_message = error_message
        await self.session.commit()
        await EventBroadcaster.publish_event(job.id, stage, progress, message)
