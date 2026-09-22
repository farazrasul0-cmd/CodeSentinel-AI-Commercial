import React, { useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  CreditCard,
  FileCode,
  FlaskConical,
  GitPullRequest,
  Github,
  Radar,
  Search,
  Server,
  Shield,
  ShieldCheck,
  Users,
} from "lucide-react";
import { QualityOverviewDashboard } from "../features/quality-overview/QualityOverviewDashboard";
import { RepositoryOnboarding } from "../features/repository-onboarding/RepositoryOnboarding";
import { AcademicBenchmarksViewer } from "../features/benchmarks/AcademicBenchmarksViewer";
import { OrgSwitcher } from "../features/commercial/OrgSwitcher";
import { TeamMembersModal } from "../features/commercial/TeamMembersModal";
import { GitHubAppConnectHub } from "../features/commercial/GitHubAppConnectHub";
import { PRReviewDetailViewer } from "../features/commercial/PRReviewDetailViewer";
import { BillingDashboard } from "../features/commercial/BillingDashboard";
import {
  MOCK_BILLING_DETAILS,
  MOCK_CONNECTED_REPOS,
  MOCK_MEMBERS,
  MOCK_ORGANIZATIONS,
  MOCK_PR_REVIEWS,
} from "../features/commercial/mockCommercialData";
import { DEMO_REPORTS } from "../shared/data/demoReports";
import { api } from "../shared/api/client";
import {
  AnalysisJob,
  AnalysisReport,
  BillingSubscriptionDetails,
  ConnectedRepo,
  Organization,
  PRReviewItem,
  TeamMember,
  UserRole,
} from "../shared/types";

type ActiveTab = "reviews" | "repositories" | "scanner" | "scorecard" | "billing" | "benchmarks";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("reviews");
  const [activeReport, setActiveReport] = useState<AnalysisReport | null>(null);

  // Multi-Tenancy & Commercial State
  const [organizations, setOrganizations] = useState<Organization[]>(MOCK_ORGANIZATIONS);
  const [currentOrg, setCurrentOrg] = useState<Organization>(MOCK_ORGANIZATIONS[0]);
  const [members, setMembers] = useState<TeamMember[]>(MOCK_MEMBERS);
  const [isTeamModalOpen, setIsTeamModalOpen] = useState(false);
  const [repositories, setRepositories] = useState<ConnectedRepo[]>(MOCK_CONNECTED_REPOS);
  const [prReviews] = useState<PRReviewItem[]>(MOCK_PR_REVIEWS);
  const [selectedReviewId, setSelectedReviewId] = useState<string>(MOCK_PR_REVIEWS[0].id);
  const [billingDetails, setBillingDetails] = useState<BillingSubscriptionDetails>(MOCK_BILLING_DETAILS);

  const handleAnalysisComplete = async (job: AnalysisJob) => {
    try {
      const report = await api.getReportByJob(job.id);
      setActiveReport(report);
      setActiveTab("scorecard");
    } catch (e) {
      console.error("Could not fetch report for completed job", e);
    }
  };

  const handleSelectReport = (report: AnalysisReport) => {
    setActiveReport(report);
    setActiveTab("scorecard");
  };

  const handleOpenScorecard = () => {
    if (!activeReport) {
      setActiveReport(DEMO_REPORTS["fastapi-realworld-example"]);
    }
    setActiveTab("scorecard");
  };

  // Team Member Management Handlers
  const handleInviteMember = (email: string, role: UserRole) => {
    const newMember: TeamMember = {
      id: `mem-${Date.now()}`,
      user_id: `usr-${Date.now()}`,
      email,
      username: email.split("@")[0],
      role,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    setMembers((prev) => [...prev, newMember]);
    setCurrentOrg((prev) => ({
      ...prev,
      active_seats_30d: prev.active_seats_30d + 1,
    }));
  };

  const handleRemoveMember = (memberId: string) => {
    setMembers((prev) => prev.filter((m) => m.id !== memberId));
    setCurrentOrg((prev) => ({
      ...prev,
      active_seats_30d: Math.max(1, prev.active_seats_30d - 1),
    }));
  };

  // Repository Setting Handlers
  const handleToggleRepoSetting = (
    repoId: string,
    setting: "pr_review_enabled" | "secret_scanning_enabled" | "quality_gate_enabled"
  ) => {
    setRepositories((prev) =>
      prev.map((r) => (r.id === repoId ? { ...r, [setting]: !r[setting] } : r))
    );
  };

  const handleUpdateThreshold = (repoId: string, minScore: number) => {
    setRepositories((prev) =>
      prev.map((r) => (r.id === repoId ? { ...r, min_rqi_score: minScore } : r))
    );
  };

  const handleSyncRepositories = () => {
    // Simulated GitHub API installation sync
    console.log("GitHub repositories synced successfully");
  };

  // Billing Handlers
  const handleUpgradePlan = (priceId: string, seats: number) => {
    console.log(`Triggering Stripe Checkout for price: ${priceId} with ${seats} seats`);
    setCurrentOrg((prev) => ({
      ...prev,
      plan: "TEAM",
      max_seats: seats,
    }));
    setBillingDetails((prev) => ({
      ...prev,
      plan: "TEAM",
      max_seats: seats,
    }));
    alert(`Stripe Checkout Session Initiated for ${seats} seats on Commercial Team plan ($${seats * 29}/mo). In production, this redirects directly to Stripe Checkout.`);
  };

  const handleOpenPortal = () => {
    console.log("Opening Stripe Customer Portal session");
    alert("Redirecting to self-serve Stripe Customer Portal for invoice downloads, tax ID updates, and card management.");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-gray-100 font-sans selection:bg-pink-500 selection:text-white">
      {/* Top Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl border-b transition-all duration-300 bg-gray-950/90 border-gray-800 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-16">
          {/* Brand & Organization Switcher */}
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setActiveTab("reviews")}
              className="flex items-center gap-2.5 text-left group"
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-pink-500 via-rose-500 to-orange-500 flex items-center justify-center text-white shadow-md shadow-pink-500/20 group-hover:scale-105 transition-transform">
                <ShieldCheck className="w-5 h-5 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                  CodeSentinel AI
                </span>
                <span className="text-[10px] text-gray-400 font-medium -mt-1 hidden sm:inline">
                  Commercial SaaS Platform
                </span>
              </div>
            </button>

            {/* Org Switcher Component */}
            <OrgSwitcher
              organizations={organizations}
              currentOrg={currentOrg}
              onSelectOrg={(org) => {
                setCurrentOrg(org);
                setBillingDetails((prev) => ({
                  ...prev,
                  plan: org.plan,
                  max_seats: org.max_seats,
                  active_seats_30d: org.active_seats_30d,
                }));
              }}
              onCreateOrg={() => {
                const name = prompt("Enter new Organization Name:");
                if (name) {
                  const newOrg: Organization = {
                    id: `org-${Date.now()}`,
                    name,
                    slug: name.toLowerCase().replace(/[^a-z0-9]/g, "-"),
                    plan: "FREE",
                    max_seats: 1,
                    active_seats_30d: 1,
                    subscription_status: "active",
                  };
                  setOrganizations((prev) => [...prev, newOrg]);
                  setCurrentOrg(newOrg);
                }
              }}
            />

            {/* Team & Seat Meter Button */}
            <button
              type="button"
              onClick={() => setIsTeamModalOpen(true)}
              className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-300 hover:text-white hover:border-gray-700 transition"
            >
              <Users className="w-3.5 h-3.5 text-pink-400" />
              <span>Seats:</span>
              <span className="font-mono text-white font-semibold">
                {currentOrg.active_seats_30d}/{currentOrg.max_seats}
              </span>
            </button>
          </div>

          {/* Functional Navigation Tabs */}
          <nav className="flex items-center space-x-1 sm:space-x-1.5">
            {/* PR Reviews Tab */}
            <button
              type="button"
              onClick={() => setActiveTab("reviews")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "reviews"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <GitPullRequest className="w-3.5 h-3.5 text-pink-400" />
              <span>PR Bot</span>
            </button>

            {/* Repositories Tab */}
            <button
              type="button"
              onClick={() => setActiveTab("repositories")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "repositories"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Server className="w-3.5 h-3.5 text-indigo-400" />
              <span className="hidden sm:inline">Repositories</span>
            </button>

            {/* Scanner Tab */}
            <button
              type="button"
              onClick={() => setActiveTab("scanner")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "scanner"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Search className="w-3.5 h-3.5 text-rose-400" />
              <span className="hidden md:inline">Deep</span> Scanner
            </button>

            {/* Live Scorecard Tab */}
            <button
              type="button"
              onClick={handleOpenScorecard}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "scorecard"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <Radar className="w-3.5 h-3.5 text-blue-400" />
              <span className="hidden md:inline">Radar</span> Scorecard
            </button>

            {/* Billing Tab */}
            <button
              type="button"
              onClick={() => setActiveTab("billing")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "billing"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <CreditCard className="w-3.5 h-3.5 text-amber-400" />
              <span>Billing</span>
            </button>

            {/* Academic Benchmarks Tab */}
            <button
              type="button"
              onClick={() => setActiveTab("benchmarks")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "benchmarks"
                  ? "bg-white/10 text-white shadow-sm border border-gray-700"
                  : "text-gray-300 hover:text-white hover:bg-white/5"
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden lg:inline">Benchmarks</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Spacer */}
      <div className="pt-16 flex-grow">
        {activeTab === "reviews" && (
          <PRReviewDetailViewer
            reviews={prReviews}
            selectedReviewId={selectedReviewId}
            onSelectReview={(id) => setSelectedReviewId(id)}
          />
        )}

        {activeTab === "repositories" && (
          <GitHubAppConnectHub
            repositories={repositories}
            onToggleSetting={handleToggleRepoSetting}
            onUpdateThreshold={handleUpdateThreshold}
            onSyncRepositories={handleSyncRepositories}
          />
        )}

        {activeTab === "scanner" && (
          <RepositoryOnboarding
            onAnalysisComplete={handleAnalysisComplete}
            onSelectReport={handleSelectReport}
            onOpenBenchmarks={() => setActiveTab("benchmarks")}
          />
        )}

        {activeTab === "billing" && (
          <BillingDashboard
            organization={currentOrg}
            billingDetails={billingDetails}
            onUpgradePlan={handleUpgradePlan}
            onOpenPortal={handleOpenPortal}
          />
        )}

        {activeTab === "benchmarks" && (
          <AcademicBenchmarksViewer onBack={() => setActiveTab("scanner")} />
        )}

        {activeTab === "scorecard" && (
          <div className="bg-[#0b0f19] text-white min-h-screen py-8">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="mb-6 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setActiveTab("scanner")}
                  className="inline-flex items-center gap-2 text-xs font-semibold text-gray-300 hover:text-white bg-gray-900/80 hover:bg-gray-800 px-3.5 py-2 rounded-lg transition-colors border border-gray-800"
                >
                  <ArrowLeft className="w-4 h-4" />
                  &larr; Back to Scanner
                </button>

                <div className="flex items-center gap-2 text-xs text-gray-400 font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Live Scorecard Mode
                </div>
              </div>

              {activeReport ? (
                <QualityOverviewDashboard
                  report={activeReport}
                  onReset={() => {
                    setActiveReport(null);
                    setActiveTab("scanner");
                  }}
                />
              ) : (
                <div className="p-16 text-center max-w-md mx-auto my-12 bg-gray-900/50 rounded-2xl border border-gray-800">
                  <Shield className="w-12 h-12 text-gray-500 mx-auto mb-3" />
                  <h3 className="text-gray-200 font-bold text-base mb-1">No Active Report Selected</h3>
                  <p className="text-xs text-gray-400 mb-6">
                    Analyze a repository in the Scanner or load an empirical baseline report.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveReport(DEMO_REPORTS["fastapi-realworld-example"]);
                    }}
                    className="px-5 py-2.5 bg-gradient-to-r from-pink-500 to-orange-500 text-white text-xs font-bold rounded-xl shadow-md hover:from-pink-600 hover:to-orange-600 transition"
                  >
                    Load Sample FastAPI Scorecard
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Team & Seat Modal */}
      <TeamMembersModal
        isOpen={isTeamModalOpen}
        onClose={() => setIsTeamModalOpen(false)}
        organization={currentOrg}
        members={members}
        onInviteMember={handleInviteMember}
        onRemoveMember={handleRemoveMember}
      />

      {/* Clean & Functional Open-Source Footer */}
      <footer className="bg-gray-950 border-t border-gray-800 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            {/* Left Brand */}
            <div className="flex flex-col sm:flex-row items-center gap-3 text-center sm:text-left">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-pink-500 to-orange-500 flex items-center justify-center text-white shadow">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  CodeSentinel AI &mdash; Commercial SaaS Platform &copy; 2026
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Multi-engine static analysis, Tree-sitter polyglot AST, and automated GitHub PR Bot
                </p>
              </div>
            </div>

            {/* Right Links */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-xs font-medium">
              <a
                href="https://github.com/farazrasul0-cmd/CodeSentinel-AI-Commercial"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-gray-400 hover:text-white transition"
              >
                <Github className="w-3.5 h-3.5" />
                <span>Commercial GitHub Repository</span>
              </a>

              <a
                href="https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-gray-400 hover:text-white transition"
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>SARIF v2.1.0 Specification</span>
              </a>

              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-gray-400 hover:text-white transition"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Swagger OpenAPI Docs (/docs)</span>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
