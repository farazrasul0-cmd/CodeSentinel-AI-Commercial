import { describe, it, expect } from "vitest";
import {
  MOCK_BILLING_DETAILS,
  MOCK_CONNECTED_REPOS,
  MOCK_MEMBERS,
  MOCK_ORGANIZATIONS,
  MOCK_PR_REVIEWS,
} from "../features/commercial/mockCommercialData";

describe("Commercial Multi-Tenancy & SaaS Features", () => {
  it("verifies organizations and active seat tracking", () => {
    expect(MOCK_ORGANIZATIONS.length).toBeGreaterThanOrEqual(3);
    const teamOrg = MOCK_ORGANIZATIONS.find((o) => o.plan === "TEAM");
    expect(teamOrg).toBeDefined();
    if (teamOrg) {
      expect(teamOrg.active_seats_30d).toBeLessThanOrEqual(teamOrg.max_seats);
      const utilization = (teamOrg.active_seats_30d / teamOrg.max_seats) * 100;
      expect(utilization).toBe(40);
    }
  });

  it("verifies member RBAC roles and permissions", () => {
    const roles = MOCK_MEMBERS.map((m) => m.role);
    expect(roles).toContain("OWNER");
    expect(roles).toContain("ADMIN");
    expect(roles).toContain("MEMBER");
    expect(roles).toContain("VIEWER");
  });

  it("verifies connected repositories and quality gate defaults", () => {
    expect(MOCK_CONNECTED_REPOS.length).toBeGreaterThanOrEqual(3);
    for (const repo of MOCK_CONNECTED_REPOS) {
      expect(repo.min_rqi_score).toBeGreaterThanOrEqual(50);
      expect(typeof repo.pr_review_enabled).toBe("boolean");
      expect(typeof repo.secret_scanning_enabled).toBe("boolean");
    }
  });

  it("evaluates PR Review Bot hunks and inline suggestion format", () => {
    expect(MOCK_PR_REVIEWS.length).toBeGreaterThanOrEqual(2);
    const prWithIssues = MOCK_PR_REVIEWS.find((pr) => pr.status === "failure");
    expect(prWithIssues).toBeDefined();
    if (prWithIssues) {
      expect(prWithIssues.critical_issues).toBeGreaterThan(0);
      const allSuggestions = prWithIssues.diff_hunks.flatMap((h) => h.suggestions);
      expect(allSuggestions.some((s) => s.severity === "CRITICAL")).toBe(true);
      expect(allSuggestions[0].suggested_patch).toBeDefined();
    }
  });

  it("verifies billing details, soft-gating calculations, and author roster", () => {
    expect(MOCK_BILLING_DETAILS.plan).toBe("TEAM");
    expect(MOCK_BILLING_DETAILS.active_authors?.length).toBe(
      MOCK_BILLING_DETAILS.active_seats_30d
    );
    expect(MOCK_BILLING_DETAILS.entitlements.allow_private_repos).toBe(true);
    expect(MOCK_BILLING_DETAILS.entitlements.allow_inline_suggestions).toBe(true);
    expect(MOCK_BILLING_DETAILS.entitlements.priority_queue).toBe(true);
  });
});
