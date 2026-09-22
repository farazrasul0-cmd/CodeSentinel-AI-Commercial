import React, { useState } from "react";
import {
  GitPullRequest,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  FileCode,
  Sparkles,
  Bot,
} from "lucide-react";
import { PRReviewItem, FindingSeverity } from "../../shared/types";

interface PRReviewDetailViewerProps {
  reviews: PRReviewItem[];
  selectedReviewId?: string;
  onSelectReview: (id: string) => void;
}

export const PRReviewDetailViewer: React.FC<PRReviewDetailViewerProps> = ({
  reviews,
  selectedReviewId,
  onSelectReview,
}) => {
  const currentPR = reviews.find((r) => r.id === selectedReviewId) || reviews[0];
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [appliedIds, setAppliedIds] = useState<Record<string, boolean>>({});

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleApplyFix = (id: string) => {
    setAppliedIds((prev) => ({ ...prev, [id]: true }));
  };

  const getSeverityBadge = (severity: FindingSeverity) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-red-950/80 text-red-300 border-red-800";
      case "HIGH":
        return "bg-amber-950/80 text-amber-300 border-amber-800";
      case "MEDIUM":
        return "bg-yellow-950/80 text-yellow-300 border-yellow-800";
      case "LOW":
        return "bg-blue-950/80 text-blue-300 border-blue-800";
      default:
        return "bg-gray-800 text-gray-300 border-gray-700";
    }
  };

  return (
    <div className="bg-[#0b0f19] text-white min-h-screen py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-pink-500/20 text-pink-400 flex items-center justify-center shadow">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Commercial PR Review Bot</h1>
              <p className="text-xs text-gray-400">
                Diff-targeted AST analysis, dual-layer secret detection, and 1-click remediation
              </p>
            </div>
          </div>

          {/* PR Selector Dropdown/Tabs */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Select PR:</span>
            <div className="flex gap-1.5 bg-gray-900 border border-gray-800 p-1 rounded-xl">
              {reviews.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => onSelectReview(r.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                    r.id === currentPR.id
                      ? "bg-white/10 text-white shadow-sm"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <GitPullRequest className="w-3 h-3 text-pink-400" />
                  <span>#{r.pr_number}</span>
                  {r.status === "success" ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Active PR Detail Card */}
        {currentPR && (
          <div className="space-y-6">
            {/* PR Overview Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-pink-400 font-bold">
                      {currentPR.repo_full_name}
                    </span>
                    <span className="text-xs text-gray-500">&bull;</span>
                    <span className="text-xs font-mono text-gray-400">PR #{currentPR.pr_number}</span>
                  </div>
                  <h2 className="text-base font-bold text-white">{currentPR.pr_title}</h2>
                  <p className="text-xs text-gray-400 mt-1">
                    Author: <span className="text-gray-200 font-mono">@{currentPR.author}</span> &bull; Commit{" "}
                    <code className="text-pink-300 bg-pink-950/40 px-1 py-0.5 rounded font-mono text-[11px]">
                      {currentPR.head_sha}
                    </code>
                  </p>
                </div>

                {/* Score & Check Run Status */}
                <div className="flex items-center gap-4">
                  {/* RQI Score Block */}
                  <div className="bg-gray-950/70 border border-gray-800 px-4 py-2.5 rounded-xl text-center">
                    <div className="text-[10px] text-gray-400 uppercase font-semibold">PR Quality Score</div>
                    <div className="flex items-center justify-center gap-1.5 mt-0.5">
                      <span className="text-2xl font-bold font-mono text-white">{currentPR.rqi_score}</span>
                      <span className="text-xs text-gray-500 font-mono">/ 100</span>
                      {currentPR.rqi_delta >= 0 ? (
                        <span className="flex items-center text-[11px] text-emerald-400 font-medium ml-1">
                          <ArrowUpRight className="w-3 h-3" />+{currentPR.rqi_delta}
                        </span>
                      ) : (
                        <span className="flex items-center text-[11px] text-red-400 font-medium ml-1">
                          <ArrowDownRight className="w-3 h-3" />
                          {currentPR.rqi_delta}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Quality Gate Status */}
                  <div
                    className={`px-4 py-3 rounded-xl border flex items-center gap-2.5 ${
                      currentPR.status === "success"
                        ? "bg-emerald-950/30 border-emerald-800/60 text-emerald-300"
                        : "bg-red-950/30 border-red-800/60 text-red-300"
                    }`}
                  >
                    {currentPR.status === "success" ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-400" />
                    )}
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider">
                        {currentPR.status === "success" ? "Quality Gate Passed" : "Quality Gate Blocked"}
                      </div>
                      <div className="text-[11px] opacity-80">
                        {currentPR.status === "success"
                          ? "Check run status: SUCCESS &bull; Ready to merge"
                          : `${currentPR.critical_issues} critical security issue(s) detected`}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bot In-Place Summary Box */}
              <div className="bg-gray-950/60 border border-gray-800/80 rounded-xl p-3.5 text-xs text-gray-300 flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-pink-400 flex-shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white">CodeSentinel AI Summary:</strong> {currentPR.summary}
                </div>
              </div>
            </div>

            {/* Diff Hunks & Inline Suggestions */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span>Changed Files &amp; Inline Remediation Suggestions</span>
              </h3>

              {currentPR.diff_hunks.map((hunk, hIdx) => (
                <div
                  key={hIdx}
                  className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-lg"
                >
                  {/* File Header */}
                  <div className="bg-gray-950 px-4 py-2.5 border-b border-gray-800 flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold text-gray-200">{hunk.file_path}</span>
                    <span className="font-mono text-[11px] text-gray-500">{hunk.hunk_header}</span>
                  </div>

                  {/* Diff Lines Table */}
                  <div className="font-mono text-xs overflow-x-auto divide-y divide-gray-800/30">
                    {hunk.lines.map((line, lIdx) => {
                      const isAdd = line.type === "add";
                      const isDel = line.type === "del";
                      return (
                        <div
                          key={lIdx}
                          className={`px-4 py-1 flex items-center gap-3 ${
                            isAdd
                              ? "bg-emerald-950/20 text-emerald-200"
                              : isDel
                              ? "bg-red-950/20 text-red-200"
                              : "text-gray-400 hover:bg-gray-800/20"
                          }`}
                        >
                          <span className="w-4 text-gray-600 select-none text-[10px]">
                            {isAdd ? "+" : isDel ? "-" : " "}
                          </span>
                          <span className="whitespace-pre">{line.content}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Inline CodeSentinel Suggestion Cards */}
                  {hunk.suggestions.map((sug) => {
                    const isApplied = appliedIds[sug.id];
                    return (
                      <div
                        key={sug.id}
                        className="m-4 bg-gray-950 border border-pink-900/40 rounded-xl p-4 space-y-3 shadow-inner"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[9px] font-mono px-2 py-0.5 rounded border font-semibold ${getSeverityBadge(
                                sug.severity
                              )}`}
                            >
                              {sug.severity}
                            </span>
                            <span className="text-xs font-bold text-white">{sug.title}</span>
                            <span className="text-[10px] text-gray-500 font-mono">[{sug.rule_id}]</span>
                          </div>
                          <span className="text-[11px] text-gray-400 font-mono">
                            Lines {sug.line_start}&ndash;{sug.line_end}
                          </span>
                        </div>

                        <p className="text-xs text-gray-300">{sug.explanation}</p>

                        {/* Native GitHub Suggestion Box */}
                        <div className="bg-[#0b0f19] border border-gray-800 rounded-lg p-3">
                          <div className="text-[10px] font-mono text-gray-500 mb-1 flex items-center justify-between">
                            <span>Suggested replacement:</span>
                            <span className="text-pink-400">```suggestion</span>
                          </div>
                          <pre className="font-mono text-xs text-emerald-300 overflow-x-auto whitespace-pre">
                            {sug.suggested_patch}
                          </pre>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center justify-end gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => handleCopy(sug.id, sug.suggested_patch)}
                            className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-medium text-gray-300 transition flex items-center gap-1.5"
                          >
                            {copiedId === sug.id ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                <span>Copied!</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5" />
                                <span>Copy Suggestion</span>
                              </>
                            )}
                          </button>

                          <button
                            type="button"
                            disabled={isApplied}
                            onClick={() => handleApplyFix(sug.id)}
                            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow ${
                              isApplied
                                ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700"
                                : "bg-gradient-to-r from-pink-500 to-indigo-500 hover:from-pink-600 hover:to-indigo-600 text-white"
                            }`}
                          >
                            {isApplied ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Committed to Branch</span>
                              </>
                            ) : (
                              <>
                                <Zap className="w-3.5 h-3.5" />
                                <span>1-Click Apply to Branch</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
