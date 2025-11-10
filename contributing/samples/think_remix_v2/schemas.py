"""Pydantic schemas for THINK Remix v2 agent outputs."""

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ImmutableModel(BaseModel):
  """Base Pydantic model with immutable configuration.

  All workflow schemas inherit from this base to ensure data immutability
  and allow extra fields for forward compatibility.
  """

  model_config = ConfigDict(
      frozen=True,
      extra='allow',
  )


class AuditResult(ImmutableModel):
  audit_status: Literal['proceed', 'block', 'request_clarification']
  question_type: Optional[
      Literal['causal', 'predictive', 'normative', 'diagnostic', 'comparative', 'hybrid']
  ] = None
  answerability: Optional[
      Literal['empirical', 'normative', 'hybrid', 'unanswerable']
  ] = None
  scope_assessment: Optional[
      Literal['appropriate', 'too_broad', 'too_narrow', 'malformed']
  ] = None
  temporal_assessment: Optional[
      Literal['feasible', 'requires_impossible_foresight', 'requires_realtime_data']
  ] = None
  reframed_question: Optional[str] = None
  clarification_needed: Optional[str] = None
  proceed_justification: Optional[str] = None


class EvidenceRequirement(ImmutableModel):
  evidence_type: str
  why_needed: str
  priority: Literal['high', 'medium', 'low'] = 'medium'


class CriticalAssumption(ImmutableModel):
  assumption: str
  risk_if_wrong: str
  linked_nulls: tuple[str, ...] = Field(default_factory=tuple)


class ResearchAxis(ImmutableModel):
  axis: str
  items: tuple[str, ...] = Field(default_factory=tuple)


class MethodologyStep(ImmutableModel):
  step: int
  focus: str
  nulls_targeted: tuple[str, ...] = Field(default_factory=tuple)


class QuestionAnalysis(ImmutableModel):
  core_question: str
  question_type: Literal[
      'causal', 'predictive', 'normative', 'diagnostic', 'comparative', 'hybrid'
  ]
  research_axes: tuple[ResearchAxis, ...] = Field(default_factory=tuple)
  required_evidence: tuple[EvidenceRequirement, ...] = Field(default_factory=tuple)
  critical_assumptions: tuple[CriticalAssumption, ...] = Field(default_factory=tuple)
  complexity_estimators: dict[str, float]
  recommended_methodology: tuple[MethodologyStep, ...] = Field(default_factory=tuple)
  handoff_summary: str


class NullHypothesis(ImmutableModel):
  hypothesis_id: str
  null_claim: str
  rejection_criteria: str
  prior_probability: float
  null_type: Optional[str] = None
  assumptions_challenged: tuple[str, ...] = Field(default_factory=tuple)


class NullHypothesisSet(ImmutableModel):
  null_hypotheses: tuple[NullHypothesis, ...]
  coverage_summary: Optional[dict[str, str]] = None


class PersonaConfig(ImmutableModel):
  id: str
  persona_name: str
  epistemological_framework: str
  analytical_focus: str
  worldview: str
  guiding_question: str
  evidence_lens: str
  time_horizon: Literal['short_term', 'medium_term', 'long_term']
  risk_orientation: Literal['risk_seeking', 'risk_neutral', 'risk_averse']
  diversity_tags: tuple[str, ...] = Field(default_factory=tuple)


class ComplexityAnalysis(ImmutableModel):
  stakeholder_count: float
  temporal_dimensions: float
  domain_crossings: float
  known_unknowns: float
  complexity_score: float
  recommended_persona_count: int


class PersonaAllocation(ImmutableModel):
  complexity_analysis: ComplexityAnalysis
  persona_count: int
  personas: tuple[PersonaConfig, ...]


class PersonaSimilarity(ImmutableModel):
  pair: tuple[str, str]
  similarity: float
  overlap_dimensions: tuple[str, ...] = Field(default_factory=tuple)


class RedundancyFlag(ImmutableModel):
  persona_ids: tuple[str, str]
  issue: str
  remediation: str


class PersonaValidation(ImmutableModel):
  validation_status: Literal['approved', 'requires_regeneration']
  cognitive_distance_matrix: tuple[PersonaSimilarity, ...] = Field(default_factory=tuple)
  redundancy_flags: tuple[RedundancyFlag, ...] = Field(default_factory=tuple)
  diversity_checks: Optional[dict[str, bool]] = None


class GatherInsightsResult(ImmutableModel):
  summary: str
  facts_registered: tuple[str, ...]
  search_strategy: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]
  coverage_metrics: Optional[dict[str, int]] = None


class PersonaEvidenceEntry(ImmutableModel):
  fact_id: str
  weight: Optional[float] = None
  rationale: Optional[str] = None
  reason: Optional[str] = None


class PersonaConclusion(ImmutableModel):
  answer: str
  confidence_percentage: float
  primary_driver: str


class PersonaAnalyticStep(ImmutableModel):
  step: str
  supporting_facts: tuple[str, ...] = Field(default_factory=tuple)
  nulls_considered: tuple[str, ...] = Field(default_factory=tuple)
  confidence_shift: Optional[float] = None


class PersonaJudgment(ImmutableModel):
  persona_id: str
  persona_name: str
  epistemological_framework: str
  conclusion: PersonaConclusion
  analytic_path: tuple[PersonaAnalyticStep, ...] = Field(default_factory=tuple)
  evidence_prioritized: tuple[PersonaEvidenceEntry, ...] = Field(default_factory=tuple)
  evidence_discounted: tuple[PersonaEvidenceEntry, ...] = Field(default_factory=tuple)
  evidence_ignored: tuple[PersonaEvidenceEntry, ...] = Field(default_factory=tuple)


class ConditionalConclusion(ImmutableModel):
  condition: str
  conclusion: str
  supporting_facts: tuple[str, ...]
  confidence: float


class SynthesisResult(ImmutableModel):
  conditional_conclusions: tuple[ConditionalConclusion, ...]
  consensus_zones: tuple[str, ...] = Field(default_factory=tuple)
  active_disagreements: tuple[str, ...] = Field(default_factory=tuple)
  evidence_map: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]


class AdversarialBlindSpot(ImmutableModel):
  fact_id: str
  credibility_score: float
  ignored_by: tuple[str, ...]
  adversarial_argument: str


class AdversarialConclusion(ImmutableModel):
  answer: str
  confidence_percentage: float
  divergence_from_majority: str


class AdversarialResult(ImmutableModel):
  exploited_blind_spots: tuple[AdversarialBlindSpot, ...] = Field(default_factory=tuple)
  adversarial_conclusion: Optional[AdversarialConclusion] = None
  notes: Optional[str] = None


class DivergencePosition(ImmutableModel):
  persona_id: str
  answer: str
  driven_by: str


class DivergenceDriver(ImmutableModel):
  disagreement_id: str
  point_of_disagreement: str
  conflict_type: str
  positions: tuple[DivergencePosition, ...]
  root_cause_type: str
  resolvability: str


class DisagreementAnalysis(ImmutableModel):
  convergence_points: tuple[str, ...] = Field(default_factory=tuple)
  divergence_drivers: tuple[DivergenceDriver, ...] = Field(default_factory=tuple)
  transcendent_insights_flagged: tuple[str, ...] = Field(default_factory=tuple)
  relevancy_hypothesis_assessment: Optional[dict[str, str]] = None


class NullAdjudication(ImmutableModel):
  null_id: str
  ruling: Literal['Reject', 'Accept', 'Undetermined']
  supporting_facts: tuple[str, ...] = Field(default_factory=tuple)
  dissenting_facts: tuple[str, ...] = Field(default_factory=tuple)
  persona_vote_summary: Optional[dict[str, int]] = None


class NullAdjudicationResult(ImmutableModel):
  null_adjudications: tuple[NullAdjudication, ...]
  skepticism_score: float
  notes: Optional[str] = None


class ResearchObjectiveResult(ImmutableModel):
  objective_id: str
  confirmatory_facts: tuple[str, ...] = Field(default_factory=tuple)
  disconfirmatory_facts: tuple[str, ...] = Field(default_factory=tuple)
  notes: Optional[str] = None


class ConductResearchResult(ImmutableModel):
  objectives_completed: tuple[ResearchObjectiveResult, ...]
  disconfirmatory_ratio: float


class PersonaIntegrity(ImmutableModel):
  persona_id: str
  coverage_ratio: float
  violations: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]
  integrity_score: float


class EvidenceConsistencyResult(ImmutableModel):
  persona_integrity: tuple[PersonaIntegrity, ...] = Field(default_factory=tuple)
  global_findings: Optional[dict[str, Any]] = None  # type: ignore[name-defined]


class EvidenceResolution(ImmutableModel):
  disagreement_id: str
  resolution: str
  winning_facts: tuple[str, ...] = Field(default_factory=tuple)
  losing_facts: tuple[str, ...] = Field(default_factory=tuple)
  justification: str


class EvidenceAdjudicationResult(ImmutableModel):
  resolution_summary: tuple[EvidenceResolution, ...]
  load_bearing_facts: tuple[str, ...] = Field(default_factory=tuple)
  unresolvable_conflicts: tuple[str, ...] = Field(default_factory=tuple)


class CaseFileSection(ImmutableModel):
  established_facts: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]


class CaseFileContest(ImmutableModel):
  disagreement_id: str
  positions: tuple[dict[str, Any], ...]  # type: ignore[name-defined]


class CaseFileAgent(ImmutableModel):
  section_1: dict[str, Any]  # type: ignore[name-defined]
  section_2: dict[str, Any]  # type: ignore[name-defined]
  section_3: dict[str, Any]  # type: ignore[name-defined]
  section_4: dict[str, Any]  # type: ignore[name-defined]
  compression_report: dict[str, Any]  # type: ignore[name-defined]


class CoverageValidationResult(ImmutableModel):
  fact_preservation_rate: float
  divergence_coverage: float
  null_coverage: float
  transcendent_insight_inclusion: float
  passed: bool
  gaps: tuple[str, ...] = Field(default_factory=tuple)


class RobustnessMetrics(ImmutableModel):
  decision_robustness_score: float
  interpretation: Literal['robust', 'moderate', 'fragile']
  components: dict[str, float]
  sensitivity_score: float
  confidence_ceiling: float
  flip_scenarios: tuple[str, ...] = Field(default_factory=tuple)
  assumption_brittleness: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]


class JustificationTrace(ImmutableModel):
  step_1_empirical_bedrock: dict[str, Any]  # type: ignore[name-defined]
  step_2_conflict_resolution: dict[str, Any]  # type: ignore[name-defined]
  step_3_uncertainty_handling: dict[str, Any]  # type: ignore[name-defined]


class FinalArbiterOutput(ImmutableModel):
  final_answer: str
  decision_robustness_score: float
  confidence_percentage: float
  confidence_ceiling: float
  justification_trace: JustificationTrace
  sensitivity_disclosure: dict[str, Any]  # type: ignore[name-defined]
  null_hypothesis_acknowledgment: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]


class QAResult(ImmutableModel):
  auditor_note_on_bedrock: str
  auditor_note_on_dissent: str
  auditor_note_on_uncertainty: str
  auditor_note_red_team_challenge: tuple[str, ...] = Field(default_factory=tuple)
  value_of_information: tuple[dict[str, Any], ...] = Field(default_factory=tuple)  # type: ignore[name-defined]

