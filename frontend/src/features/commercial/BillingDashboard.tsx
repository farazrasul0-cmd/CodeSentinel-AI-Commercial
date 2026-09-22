import React, { useState } from "react";
import {
  CreditCard,
  CheckCircle2,
  ExternalLink,
  Zap,
  Users,
  AlertCircle,
  Layers,
  ArrowRight,
} from "lucide-react";
import { BillingSubscriptionDetails, Organization } from "../../shared/types";

interface BillingDashboardProps {
  organization: Organization;
  billingDetails: BillingSubscriptionDetails;
  onUpgradePlan: (priceId: string, seats: number) => void;
  onOpenPortal: () => void;
}

export const BillingDashboard: React.FC<BillingDashboardProps> = ({
  organization,
  billingDetails,
  onUpgradePlan,
  onOpenPortal,
}) => {
  const [selectedSeats, setSelectedSeats] = useState(organization.max_seats || 5);
  const [isProcessing, setIsProcessing] = useState(false);

  const percentSeatsUsed = Math.min(
    100,
    Math.round((billingDetails.active_seats_30d / billingDetails.max_seats) * 100)
  );

  const percentScansUsed = Math.min(
    100,
    Math.round((billingDetails.monthly_scans_used / billingDetails.max_monthly_scans) * 100)
  );

  const isOverLimit = billingDetails.active_seats_30d > billingDetails.max_seats;

  const handleUpgrade = (priceId: string) => {
    setIsProcessing(true);
    onUpgradePlan(priceId, selectedSeats);
    setTimeout(() => setIsProcessing(false), 2000);
  };

  return (
    <div className="bg-[#0b0f19] text-white min-h-screen py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center shadow">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Subscription &amp; Usage Metering</h1>
              <p className="text-xs text-gray-400">
                Stripe Billing &bull; Active PR Contributor Seat Metering &bull; Tier Entitlements
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onOpenPortal}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-xs font-semibold text-gray-200 rounded-xl transition flex items-center gap-2 shadow"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Customer Billing Portal</span>
            </button>
          </div>
        </div>

        {/* Soft-Gating Alert If Over Limit */}
        {isOverLimit && (
          <div className="bg-amber-950/40 border border-amber-800/80 rounded-2xl p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-amber-200 uppercase tracking-wide">
                Active Seat Overage Detected (Soft-Gating Active)
              </h4>
              <p className="text-xs text-amber-300/90 mt-1">
                Your organization has {billingDetails.active_seats_30d} active PR contributors in the last 30
                days, exceeding your {billingDetails.max_seats}-seat tier. CodeSentinel AI is maintaining
                uninterrupted PR scanning for your team, but please adjust your seat count below.
              </p>
            </div>
          </div>
        )}

        {/* Meters Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Current Tier Summary */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <span className="text-[10px] uppercase font-semibold text-gray-400 tracking-wider">
                Current Plan
              </span>
              <div className="flex items-center justify-between mt-2">
                <span className="text-2xl font-bold font-mono text-white">
                  {billingDetails.plan} Tier
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800 text-emerald-300">
                  {billingDetails.subscription_status}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                {billingDetails.plan === "TEAM"
                  ? "$29 / active contributor / month"
                  : billingDetails.plan === "ENTERPRISE"
                  ? "Custom enterprise agreement"
                  : "Free tier (Community)"}
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-gray-800 text-xs text-gray-400 flex items-center justify-between">
              <span>Renewal Cycle</span>
              <span className="font-mono text-gray-200">Monthly auto-renew</span>
            </div>
          </div>

          {/* Active 30-Day PR Contributor Seat Meter */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-semibold text-gray-400 tracking-wider">
                  Active PR Contributors (30d)
                </span>
                <Users className="w-4 h-4 text-pink-400" />
              </div>

              <div className="flex items-baseline gap-1 mt-2">
                <span className="text-3xl font-bold font-mono text-white">
                  {billingDetails.active_seats_30d}
                </span>
                <span className="text-sm font-mono text-gray-400">
                  / {billingDetails.max_seats} seats
                </span>
              </div>

              {/* Progress Bar */}
              <div className="mt-3 w-full h-2 bg-gray-950 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isOverLimit
                      ? "bg-amber-500"
                      : "bg-gradient-to-r from-pink-500 to-indigo-500"
                  }`}
                  style={{ width: `${percentSeatsUsed}%` }}
                />
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-gray-800 text-xs text-gray-400 flex items-center justify-between">
              <span>Seat Utilization</span>
              <span className="font-mono font-medium text-white">{percentSeatsUsed}% capacity</span>
            </div>
          </div>

          {/* Monthly Scans Quota */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-semibold text-gray-400 tracking-wider">
                  Monthly Scans Used
                </span>
                <Layers className="w-4 h-4 text-indigo-400" />
              </div>

              <div className="flex items-baseline gap-1 mt-2">
                <span className="text-3xl font-bold font-mono text-white">
                  {billingDetails.monthly_scans_used}
                </span>
                <span className="text-sm font-mono text-gray-400">
                  / {billingDetails.max_monthly_scans}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="mt-3 w-full h-2 bg-gray-950 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                  style={{ width: `${percentScansUsed}%` }}
                />
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-gray-800 text-xs text-gray-400 flex items-center justify-between">
              <span>Quota Remaining</span>
              <span className="font-mono font-medium text-white">
                {billingDetails.max_monthly_scans - billingDetails.monthly_scans_used} scans
              </span>
            </div>
          </div>
        </div>

        {/* Active Authors Roster */}
        {billingDetails.active_authors && billingDetails.active_authors.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <Users className="w-4 h-4 text-pink-400" />
              <span>30-Day Active PR Contributor Roster (Metered Seats)</span>
            </h3>
            <p className="text-xs text-gray-400">
              Only developers who authored at least one PR reviewed by CodeSentinel AI in the trailing 30 days consume a seat.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              {billingDetails.active_authors.map((author, idx) => (
                <div
                  key={idx}
                  className="bg-gray-950/70 border border-gray-800/80 rounded-xl p-3 flex items-center gap-2.5"
                >
                  <div className="w-7 h-7 rounded-full bg-pink-500/20 text-pink-400 font-bold flex items-center justify-center text-xs">
                    {author.github_author.charAt(0).toUpperCase()}
                  </div>
                  <div className="truncate">
                    <div className="text-xs font-semibold text-white truncate">
                      @{author.github_author}
                    </div>
                    <div className="text-[10px] text-gray-500">
                      Active {new Date(author.last_pr_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pricing Tiers Comparison */}
        <div className="space-y-4">
          <div className="text-center max-w-xl mx-auto space-y-1">
            <h2 className="text-base font-bold text-white">Upgrade or Customize Your Plan</h2>
            <p className="text-xs text-gray-400">
              Transparent per-seat pricing. No charge for passive code readers or reviewers.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
            {/* Free Tier */}
            <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-bold text-gray-200">Community / Free</h3>
                <div className="mt-3">
                  <span className="text-2xl font-bold font-mono text-white">$0</span>
                  <span className="text-xs text-gray-400"> / forever</span>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  For individual open-source maintainers and students.
                </p>

                <ul className="mt-6 space-y-2.5 text-xs text-gray-300">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />
                    <span>1 Active Seat</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />
                    <span>Public Repositories Only</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />
                    <span>Standard Queue Priority</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />
                    <span>50 scans / month</span>
                  </li>
                </ul>
              </div>

              <button
                type="button"
                disabled={billingDetails.plan === "FREE"}
                className="mt-6 w-full py-2.5 rounded-xl border border-gray-700 bg-gray-800 text-xs font-semibold text-gray-300 cursor-not-allowed"
              >
                {billingDetails.plan === "FREE" ? "Current Plan" : "Downgrade"}
              </button>
            </div>

            {/* Team Tier */}
            <div className="bg-gradient-to-b from-gray-900 to-indigo-950/30 border-2 border-pink-500 rounded-2xl p-6 flex flex-col justify-between relative shadow-2xl">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-pink-500 to-indigo-500 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-0.5 rounded-full shadow">
                Most Popular for Teams
              </div>

              <div>
                <h3 className="text-sm font-bold text-white">Commercial Team</h3>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-3xl font-bold font-mono text-white">$29</span>
                  <span className="text-xs text-gray-300"> / active contributor / mo</span>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Full PR bot automation, private repo security, and 1-click remediation.
                </p>

                <ul className="mt-6 space-y-2.5 text-xs text-gray-200">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span>Unlimited Private &amp; Public Repos</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span>1-Click Native GitHub Suggestions</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span>Dual-Layer Secret Detection (Shannon Entropy)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span>Priority Low-Latency Celery Lane (&lt;60s SLA)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span>1,000 scans / month</span>
                  </li>
                </ul>
              </div>

              <div className="mt-6 space-y-3">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>Seats:</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedSeats(Math.max(1, selectedSeats - 1))}
                      className="w-6 h-6 rounded bg-gray-800 text-gray-200 hover:bg-gray-700 font-bold"
                    >
                      -
                    </button>
                    <span className="font-mono font-bold text-white">{selectedSeats}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedSeats(selectedSeats + 1)}
                      className="w-6 h-6 rounded bg-gray-800 text-gray-200 hover:bg-gray-700 font-bold"
                    >
                      +
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleUpgrade("price_team_monthly")}
                  disabled={isProcessing}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-500 hover:from-pink-600 hover:to-indigo-600 text-xs font-bold text-white transition flex items-center justify-center gap-2 shadow-lg"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>
                    {billingDetails.plan === "TEAM"
                      ? `Update Seats (${selectedSeats * 29}/mo)`
                      : `Upgrade to Team ($${selectedSeats * 29}/mo)`}
                  </span>
                </button>
              </div>
            </div>

            {/* Enterprise Tier */}
            <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-bold text-gray-200">Enterprise Dedicated</h3>
                <div className="mt-3">
                  <span className="text-2xl font-bold font-mono text-white">Custom</span>
                  <span className="text-xs text-gray-400"> / annual billing</span>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  For large engineering orgs requiring VPC sandboxes and SOC2 compliance.
                </p>

                <ul className="mt-6 space-y-2.5 text-xs text-gray-300">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                    <span>Everything in Team + Unlimited Seats</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                    <span>Single-Tenant Dedicated Sandbox Cluster</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                    <span>SAML / Okta SSO &amp; SCIM Provisioning</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                    <span>Custom Tree-sitter &amp; Semgrep AST Rules</span>
                  </li>
                </ul>
              </div>

              <a
                href="mailto:enterprise@codesentinel.ai?subject=Enterprise%20Plan%20Inquiry"
                className="mt-6 w-full py-2.5 rounded-xl border border-indigo-700 bg-indigo-950/60 hover:bg-indigo-900 text-xs font-semibold text-indigo-300 text-center transition flex items-center justify-center gap-2"
              >
                <span>Contact Enterprise Sales</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
