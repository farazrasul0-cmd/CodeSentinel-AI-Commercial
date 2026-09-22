import React, { useState } from "react";
import {
  Github,
  CheckCircle2,
  Lock,
  Globe,
  RefreshCw,
  ExternalLink,
  Bot,
  KeyRound,
  ShieldAlert,
  Search,
} from "lucide-react";
import { ConnectedRepo } from "../../shared/types";

interface GitHubAppConnectHubProps {
  repositories: ConnectedRepo[];
  onToggleSetting: (
    repoId: string,
    setting: "pr_review_enabled" | "secret_scanning_enabled" | "quality_gate_enabled"
  ) => void;
  onUpdateThreshold: (repoId: string, minScore: number) => void;
  onSyncRepositories: () => void;
}

export const GitHubAppConnectHub: React.FC<GitHubAppConnectHubProps> = ({
  repositories,
  onToggleSetting,
  onUpdateThreshold,
  onSyncRepositories,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);

  const filteredRepos = repositories.filter(
    (r) =>
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.full_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSync = () => {
    setIsSyncing(true);
    onSyncRepositories();
    setTimeout(() => setIsSyncing(false), 1200);
  };

  return (
    <div className="bg-[#0b0f19] text-white min-h-screen py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* GitHub App Connection Banner */}
        <div className="bg-gradient-to-r from-gray-900 via-gray-900 to-indigo-950/40 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center text-white shadow-md">
              <Github className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white">CodeSentinel GitHub App</h2>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                  <CheckCircle2 className="w-3 h-3" />
                  App Installed &amp; Synced
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Webhook listener active. Scans PRs automatically using diff-scoped ASTs and posts inline remediation comments.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSync}
              disabled={isSyncing}
              className="px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-xs font-semibold text-gray-200 transition flex items-center gap-1.5 shadow"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin text-pink-400" : ""}`} />
              <span>{isSyncing ? "Syncing Repos..." : "Sync Repositories"}</span>
            </button>
            <a
              href="https://github.com/apps/codesentinel-ai/installations/new"
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-500 hover:from-pink-600 hover:to-indigo-600 text-xs font-semibold text-white transition flex items-center gap-1.5 shadow"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Configure on GitHub</span>
            </a>
          </div>
        </div>

        {/* Search & Stats Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter repositories..."
              className="w-full bg-gray-900 border border-gray-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
            />
          </div>
          <div className="text-xs text-gray-400 font-mono">
            Showing <strong className="text-white">{filteredRepos.length}</strong> connected repositories
          </div>
        </div>

        {/* Repositories Grid */}
        <div className="grid grid-cols-1 gap-4">
          {filteredRepos.map((repo) => (
            <div
              key={repo.id}
              className="bg-gray-900/70 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-800/80 pb-3">
                <div className="flex items-center gap-2.5">
                  {repo.private ? (
                    <span className="p-1.5 rounded-lg bg-amber-950/40 text-amber-400 border border-amber-800/50">
                      <Lock className="w-3.5 h-3.5" />
                    </span>
                  ) : (
                    <span className="p-1.5 rounded-lg bg-blue-950/40 text-blue-400 border border-blue-800/50">
                      <Globe className="w-3.5 h-3.5" />
                    </span>
                  )}
                  <div>
                    <h3 className="text-sm font-semibold text-white hover:text-pink-400 transition cursor-pointer">
                      {repo.full_name}
                    </h3>
                    <p className="text-[11px] text-gray-400">
                      Last analyzed {repo.last_analyzed_at || "recently"} &bull; {repo.active_prs_count} open PRs
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-gray-400">Min RQI Quality Gate:</span>
                  <input
                    type="number"
                    min="50"
                    max="100"
                    value={repo.min_rqi_score}
                    onChange={(e) => onUpdateThreshold(repo.id, Number(e.target.value))}
                    className="w-16 bg-gray-950 border border-gray-800 rounded-lg px-2 py-1 text-xs text-center text-white focus:outline-none focus:border-pink-500 font-mono"
                  />
                  <span className="text-xs text-gray-500 font-mono">/ 100</span>
                </div>
              </div>

              {/* Toggles Row */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* PR Review Toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-950/60 border border-gray-800/60">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-pink-400" />
                    <div>
                      <div className="text-xs font-medium text-gray-200">PR Review Bot</div>
                      <div className="text-[10px] text-gray-500">Diff-scoped AST comments</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onToggleSetting(repo.id, "pr_review_enabled")}
                    className={`w-10 h-5 flex items-center rounded-full p-1 cursor-pointer transition-colors ${
                      repo.pr_review_enabled ? "bg-pink-600 justify-end" : "bg-gray-800 justify-start"
                    }`}
                  >
                    <div className="bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition" />
                  </button>
                </div>

                {/* Secret Scanning Toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-950/60 border border-gray-800/60">
                  <div className="flex items-center gap-2">
                    <KeyRound className="w-4 h-4 text-amber-400" />
                    <div>
                      <div className="text-xs font-medium text-gray-200">Secret Scanner</div>
                      <div className="text-[10px] text-gray-500">Signatures + Shannon entropy</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onToggleSetting(repo.id, "secret_scanning_enabled")}
                    className={`w-10 h-5 flex items-center rounded-full p-1 cursor-pointer transition-colors ${
                      repo.secret_scanning_enabled ? "bg-amber-600 justify-end" : "bg-gray-800 justify-start"
                    }`}
                  >
                    <div className="bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition" />
                  </button>
                </div>

                {/* Quality Gate Toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-950/60 border border-gray-800/60">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-indigo-400" />
                    <div>
                      <div className="text-xs font-medium text-gray-200">GitHub Check Run</div>
                      <div className="text-[10px] text-gray-500">Block merge if score &lt; {repo.min_rqi_score}</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onToggleSetting(repo.id, "quality_gate_enabled")}
                    className={`w-10 h-5 flex items-center rounded-full p-1 cursor-pointer transition-colors ${
                      repo.quality_gate_enabled ? "bg-indigo-600 justify-end" : "bg-gray-800 justify-start"
                    }`}
                  >
                    <div className="bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
