from __future__ import annotations

from abc import ABC, abstractmethod

from pr_agents.models import (
    AnalysisRequest,
    AnalysisResult,
    ChartArtifact,
    DatasetRef,
    ReportArtifact,
    TaskContext,
)


class DataIngestionService(ABC):
    @abstractmethod
    def parse_file(
        self,
        context: TaskContext,
        file_name: str,
        content: str,
        business_code: str,
        source_profile: dict,
    ) -> DatasetRef:
        raise NotImplementedError

    @abstractmethod
    def query_database(
        self,
        context: TaskContext,
        query_name: str,
        sql: str,
        business_code: str,
        source_profile: dict,
    ) -> DatasetRef:
        raise NotImplementedError


class DataPreparationService(ABC):
    @abstractmethod
    def clean_data(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        operations: list[str],
        business_code: str,
        clean_profile: dict,
    ) -> DatasetRef:
        raise NotImplementedError


class AnalysisService(ABC):
    @abstractmethod
    def analyze_data(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        raise NotImplementedError


class VisualizationService(ABC):
    @abstractmethod
    def build_chart(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        analysis: AnalysisResult,
        request: AnalysisRequest,
    ) -> ChartArtifact:
        raise NotImplementedError


class ReportService(ABC):
    @abstractmethod
    def generate_report(
        self,
        context: TaskContext,
        dataset: DatasetRef | None,
        analysis: AnalysisResult,
        chart: ChartArtifact | None,
        request: AnalysisRequest,
    ) -> ReportArtifact:
        raise NotImplementedError


class AnalysisPlatform(
    DataIngestionService,
    DataPreparationService,
    AnalysisService,
    VisualizationService,
    ReportService,
    ABC,
):
    """Composite interface used by workflows and ready for QT adaptation."""
