export type JobStatus =
  | "QUEUED"
  | "CLONING"
  | "INDEXING"
  | "STATIC_ANALYSIS"
  | "DEFECT_PREDICTION"
  | "AI_REVIEW"
  | "AGGREGATING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type FindingSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type FindingCategory = "SECURITY" | "CODE_SMELL" | "BUG_RISK" | "PERFORMANCE" | "MAINTAINABILITY" | "ARCHITECTURE";
export type RiskTier = "CRITICAL" | "HIGH" | "MODERATE" | "LOW";

// Commercial RBAC & Billing Types
export type UserRole = "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";
export type OrgPlan = "FREE" | "TEAM" | "ENTERPRISE";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: OrgPlan;
  max_seats: number;
  active_seats_30d: number;
  subscription_status: string;
  avatar_url?: string;
}

export interface TeamMember {
  id: string;
  user_id: string;
  email: string;
  username: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface ConnectedRepo {
  id: string;
  name: string;
  full_name: string;
  private: boolean;
  pr_review_enabled: boolean;
  secret_scanning_enabled: boolean;
  quality_gate_enabled: boolean;
  min_rqi_score: number;
  active_prs_count: number;
  last_analyzed_at?: string;
}

export interface PRDiffLine {
  type: "add" | "del" | "context";
  content: string;
  old_line?: number;
  new_line?: number;
}

export interface PRInlineSuggestion {
  id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  severity: FindingSeverity;
  rule_id: string;
  title: string;
  explanation: string;
  suggested_patch: string;
  applied?: boolean;
}

export interface PRDiffHunk {
  file_path: string;
  hunk_header: string;
  lines: PRDiffLine[];
  suggestions: PRInlineSuggestion[];
}

export interface PRReviewItem {
  id: string;
  pr_number: number;
  pr_title: string;
  repo_full_name: string;
  author: string;
  head_sha: string;
  base_sha: string;
  status: "success" | "failure" | "pending";
  rqi_score: number;
  rqi_delta: number;
  inline_comments_count: number;
  critical_issues: number;
  summary: string;
  diff_hunks: PRDiffHunk[];
  created_at: string;
}

export interface BillingSubscriptionDetails {
  organization_id: string;
  plan: OrgPlan;
  subscription_status: string;
  max_seats: number;
  active_seats_30d: number;
  monthly_scans_used: number;
  max_monthly_scans: number;
  entitlements: {
    allow_private_repos: boolean;
    allow_inline_suggestions: boolean;
    allow_secret_scanning: boolean;
    allow_custom_rules: boolean;
    priority_queue: boolean;
  };
  active_authors?: {
    github_author: string;
    last_pr_at: string;
  }[];
}

export interface Repository {
  id: string;
  url: string;
  name: string;
  description?: string;
  default_branch: string;
  primary_language?: string;
  languages: Record<string, number>;
  disk_size_bytes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnalysisJob {
  id: string;
  repository_id: string;
  branch: string;
  commit_sha?: string;
  status: JobStatus;
  current_stage: string;
  progress_percent: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface Issue {
  id: string;
  rule_id: string;
  category: FindingCategory;
  severity: FindingSeverity;
  file_path: string;
  line_start: number;
  line_end: number;
  title: string;
  description: string;
  snippet?: string;
  remediation?: string;
  cwe_id?: string;
}

export interface FileMetric {
  id: string;
  file_path: string;
  language?: string;
  sloc: number;
  cyclomatic_complexity: number;
  cognitive_complexity: number;
  function_count: number;
  class_count: number;
  maintainability_index: number;
  halstead_metrics: Record<string, any>;
}

export interface ShapFactor {
  feature_name: string;
  display_name: string;
  feature_value: number;
  shap_value: number;
  impact_direction: "INCREASES_RISK" | "DECREASES_RISK";
  percentage: number;
  remediation: string;
}

export interface ShapExplanation {
  base_value: number;
  predicted_probability: number;
  dominant_factor: string;
  summary: string;
  factors: ShapFactor[];
}

export interface DefectSummary {
  total_files_analyzed: number;
  critical_count: number;
  high_count: number;
  moderate_count: number;
  low_count: number;
  average_defect_probability: number;
  highest_risk_file?: string;
  highest_risk_probability: number;
}

export interface DefectPrediction {
  id: string;
  file_path: string;
  defect_probability: number;
  risk_tier: RiskTier;
  model_version: string;
  shap_factors: ShapExplanation | Record<string, any>;
}

export type CommentStatus = "PENDING" | "ACCEPTED" | "DISMISSED";

export interface ReviewComment {
  id: string;
  report_id: string;
  file_path: string;
  line_number: number;
  comment: string;
  suggested_patch?: string;
  status: CommentStatus;
  created_at: string;
}

export interface AnalysisReport {
  id: string;
  job_id: string;
  overall_score: number;
  maintainability_score: number;
  security_score: number;
  testing_score: number;
  architecture_score: number;
  total_files: number;
  total_lines_of_code: number;
  total_functions: number;
  total_classes: number;
  technical_debt_minutes: number;
  summary_metadata: Record<string, any>;
  created_at: string;
  issues: Issue[];
  file_metrics: FileMetric[];
  defect_predictions: DefectPrediction[];
  review_comments?: ReviewComment[];
}

export interface RadarAxisPoint {
  axis: string;
  value: number;
  benchmark_value: number;
}

export interface PillarScore {
  name: string;
  score: number;
  weight: number;
  weighted_contribution: number;
  grade: "A" | "B" | "C" | "D" | "F";
  benchmark_percentile: number;
  summary: string;
}

export interface RecommendationItem {
  rank: number;
  pillar: string;
  title: string;
  description: string;
  effort_minutes: number;
  potential_score_impact: number;
}

export interface RadarScorecardResponse {
  report_id: string;
  overall_score: number;
  grade: "A" | "B" | "C" | "D" | "F";
  radar_data: RadarAxisPoint[];
  pillars: PillarScore[];
  technical_debt_minutes: number;
  recommendations: RecommendationItem[];
  false_positives_suppressed: number;
  calculated_at: string;
}

export interface ScorecardTrendPoint {
  report_id: string;
  commit_hash?: string;
  analyzed_at: string;
  overall_score: number;
  maintainability_score: number;
  security_score: number;
  architecture_score: number;
  testing_score: number;
}

export interface ScorecardTrendResponse {
  repository_id: string;
  repository_name: string;
  points: ScorecardTrendPoint[];
  trend_direction: "IMPROVING" | "STABLE" | "DEGRADING";
  delta_since_previous: number;
}

export interface BenchmarkExperimentRQ1 {
  description: string;
  hybrid_precision: number;
  hybrid_recall: number;
  hybrid_f1_score: number;
  static_baseline_precision: number;
  static_baseline_recall: number;
  static_baseline_f1_score: number;
  f1_gain_percentage: number;
}

export interface BenchmarkExperimentRQ2 {
  description: string;
  total_files: number;
  total_loc: number;
  recall_at_top_20_percent_loc: number;
  random_baseline_recall: number;
  cost_effectiveness_multiplier: number;
}

export interface BenchmarkExperimentRQ3 {
  description: string;
  benign_test_fixture_alerts_total: number;
  false_positives_suppressed_count: number;
  false_positive_suppression_rate: number;
  critical_security_vulnerabilities_total: number;
  critical_vulnerabilities_retained_count: number;
  critical_vulnerability_retention_rate: number;
}

export interface BenchmarkSuiteResult {
  evaluation_timestamp: string;
  corpus_size: number;
  total_loc_evaluated: number;
  rq1_triangulation_accuracy: BenchmarkExperimentRQ1;
  rq2_effort_aware_ranking: BenchmarkExperimentRQ2;
  rq3_false_positive_suppression: BenchmarkExperimentRQ3;
  conclusion: string;
}
