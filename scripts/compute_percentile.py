import os
import math
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

# Authenticated viewer context captures private repositories, restricted org commits, and reviews
QUERY = """
query {
  viewer {
    login
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
    }
    repositoriesContributedTo(first: 100, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
      totalCount
    }
    pullRequests(states: [MERGED, OPEN]) {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
      nodes {
        stargazerCount
      }
    }
  }
}
"""

def fetch_data():
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": QUERY}, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"GraphQL request failed [{response.status_code}]: {response.text}")

    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors returned: {payload['errors']}")

    return payload["data"]["viewer"]

def standard_normal_cdf(x):
    """Cumulative distribution function for the standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def compute_metrics(data):
    cc = data["contributionsCollection"]

    # Public activity
    public_commits = cc["totalCommitContributions"]
    prs = cc["totalPullRequestContributions"]
    reviews = cc["totalPullRequestReviewContributions"]
    issues = cc["totalIssueContributions"]
    public_total = public_commits + prs + reviews + issues

    # Private and Organization activity
    private_commits = cc.get("restrictedContributionsCount", 0)
    all_commits = public_commits + private_commits
    grand_total = max(1, public_total + private_commits)

    # Split percentages
    public_pct = round((public_total / grand_total) * 100, 1)
    private_pct = round((private_commits / grand_total) * 100, 1)

    # Segmented progress bar width (total width = 445px)
    total_bar_w = 445
    public_bar_w = round((public_total / grand_total) * total_bar_w)
    private_bar_w = total_bar_w - public_bar_w

    # External collaboration signals
    repos_contributed = data["repositoriesContributedTo"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in data["repositories"]["nodes"])

    # --- AI-Era Recalibrated Scoring Model ---
    # 1. Commits: Square-root damping suppresses automated agent micro-commit spam.
    commit_score = 15.0 * math.sqrt(max(0, all_commits))

    # 2. PRs: Cohesive units of shipped work.
    pr_score = prs * 4.0

    # 3. Reviews: Human-in-the-loop verification and architectural oversight.
    review_score = reviews * 7.0

    # 4. Issues: Problem formulation, edge cases, and triage.
    issue_score = issues * 2.0

    # 5. Ecosystem validation (stars capped to prevent vanity skew).
    star_score = min(500.0, stars * 1.0)

    base_score = commit_score + pr_score + review_score + issue_score + star_score

    # Cross-repository breadth multiplier (up to +30%)
    breadth_factor = 1.0 + min(0.30, math.log10(max(1, repos_contributed)) * 0.12)
    composite_score = base_score * breadth_factor

    # --- Calibrated Log-Normal CDF vs. Active Developers (~8M engineers) ---
    mu = 6.1      # Calibrated median active composite score (~450)
    sigma = 1.15   # Models realistic heavy-tail distribution

    z = (math.log(max(1.0, composite_score)) - mu) / sigma
    percentile = standard_normal_cdf(z) * 100.0
    top_percentage = max(0.05, round(100.0 - percentile, 2))

    # Seniority & Output Tiers
    if top_percentage <= 1.0:
        tier = "S+"
    elif top_percentage <= 3.5:
        tier = "S"
    elif top_percentage <= 10.0:
        tier = "A+"
    elif top_percentage <= 25.0:
        tier = "A"
    elif top_percentage <= 50.0:
        tier = "B"
    else:
        tier = "C"

    return {
        "commits": all_commits,
        "prs": prs,
        "reviews": reviews,
        "issues": issues,
        "score": round(composite_score),
        "percentile": round(percentile, 1),
        "top_percentage": top_percentage,
        "tier": tier,
        "public_total": public_total,
        "private_total": private_commits,
        "public_pct": public_pct,
        "private_pct": private_pct,
        "public_bar_w": public_bar_w,
        "private_bar_w": private_bar_w,
    }

def generate_svg(m):
    svg = f"""<svg width="495" height="240" viewBox="0 0 495 240" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 17px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .subtitle {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #7970a9; }}
    .stat-label {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .stat-val {{ font: 700 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .rank-text {{ font: 700 32px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d847; }}
    .rank-sub {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .split-title {{ font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .legend-public {{ font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .legend-private {{ font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
  </style>

  <rect width="495" height="240" rx="10" fill="#141321" stroke="#fe428e" stroke-width="1"/>
  
  <text x="25" y="30" class="header">GitHub Standing (Active Developer Index)</text>
  <text x="25" y="46" class="subtitle">AI-era calibrated: human reviews, PR shipping &amp; sublinear commits</text>
  
  <text x="25" y="76" class="stat-label">Total Commits (All Repos):</text>
  <text x="245" y="76" class="stat-val">{m['commits']:,}</text>
  
  <text x="25" y="98" class="stat-label">Pull Requests Merged/Open:</text>
  <text x="245" y="98" class="stat-val">{m['prs']:,}</text>
  
  <text x="25" y="120" class="stat-label">Code Reviews Given:</text>
  <text x="245" y="120" class="stat-val">{m['reviews']:,}</text>
  
  <text x="25" y="142" class="stat-label">Issues Triaged &amp; Opened:</text>
  <text x="245" y="142" class="stat-val">{m['issues']:,}</text>

  <text x="25" y="164" class="stat-label">Global Standing:</text>
  <text x="245" y="164" class="stat-val">Top {m['top_percentage']}% ({m['percentile']}th percentile)</text>

  <!-- Circular Tier Badge -->
  <circle cx="410" cy="98" r="42" stroke="#fe428e" stroke-width="3" fill="#1a1829"/>
  <text x="410" y="108" text-anchor="middle" class="rank-text">{m['tier']}</text>
  <text x="410" y="156" text-anchor="middle" class="rank-sub">Top {m['top_percentage']}%</text>

  <!-- Split Ratio Header -->
  <text x="25" y="196" class="split-title">Contribution Split</text>
  <text x="180" y="196" class="legend-public">● Public: {m['public_pct']}% ({m['public_total']:,})</text>
  <text x="325" y="196" class="legend-private">● Private &amp; Org: {m['private_pct']}% ({m['private_total']:,})</text>

  <!-- Segmented Dual-Tone Progress Bar -->
  <clipPath id="bar-clip">
    <rect x="25" y="208" width="445" height="10" rx="5"/>
  </clipPath>
  
  <g clip-path="url(#bar-clip)">
    <rect x="25" y="208" width="445" height="10" fill="#242238"/>
    <rect x="25" y="208" width="{m['public_bar_w']}" height="10" fill="#a9fef7"/>
    <rect x="{25 + m['public_bar_w']}" y="208" width="{m['private_bar_w']}" height="10" fill="#fe428e"/>
  </g>
</svg>"""

    with open("percentile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    data = fetch_data()
    metrics = compute_metrics(data)
    generate_svg(metrics)
    print(f"Metrics generated successfully:")
    print(f"- Standing: Top {metrics['top_percentage']}% (Tier {metrics['tier']}, Score {metrics['score']})")
    print(f"- Split: {metrics['public_pct']}% Public ({metrics['public_total']}) | {metrics['private_pct']}% Private & Org ({metrics['private_total']})")
