import os
import math
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

# Query authenticated viewer to capture private, enterprise, and org data
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
    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": QUERY}, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.status_code}, {response.text}")
    res_json = response.json()
    if "errors" in res_json:
        raise Exception(f"GraphQL Errors: {res_json['errors']}")
    return res_json["data"]["viewer"]

def standard_normal_cdf(x):
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def compute_ai_era_percentile(data):
    cc = data["contributionsCollection"]
    
    # Raw counts (including private & restricted org contributions)
    commits = cc["totalCommitContributions"] + cc.get("restrictedContributionsCount", 0)
    prs = cc["totalPullRequestContributions"]
    reviews = cc["totalPullRequestReviewContributions"]
    issues = cc["totalIssueContributions"]
    repos_contributed = data["repositoriesContributedTo"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in data["repositories"]["nodes"])

    # --- AI-Era Weighting Scheme ---
    # Commits: discounted (micro-commits & agent loops are cheap)
    # PRs: high value (shipping cohesive features)
    # Reviews: highest value (human verification & code governance)
    # Issues: problem specification & triage
    base_score = (
        (commits * 0.5) +
        (prs * 3.5) +
        (reviews * 6.0) +
        (issues * 2.0) +
        (stars * 0.5)
    )

    # Breadth multiplier: rewards cross-repo/cross-org impact (up to +35%)
    breadth_factor = 1.0 + min(0.35, math.log10(max(1, repos_contributed)) * 0.15)
    adjusted_score = base_score * breadth_factor

    # --- Log-Normal CDF Calibrated to Active GitHub Developers (~8M active population) ---
    # mu = 6.8 corresponds to a median active score of ~900
    # sigma = 1.35 accounts for heavy-tailed open source/staff engineer distributions
    mu = 6.8
    sigma = 1.35

    z_score = (math.log(max(1.0, adjusted_score)) - mu) / sigma
    percentile = standard_normal_cdf(z_score) * 100.0
    
    # Top % standing
    top_percentage = max(0.01, round(100.0 - percentile, 2))

    # Strict Tier thresholds against active population
    if top_percentage <= 0.5:
        tier = "S+"
    elif top_percentage <= 2.0:
        tier = "S"
    elif top_percentage <= 7.0:
        tier = "A+"
    elif top_percentage <= 18.0:
        tier = "A"
    elif top_percentage <= 40.0:
        tier = "B"
    else:
        tier = "C"

    return {
        "commits": commits,
        "prs": prs,
        "reviews": reviews,
        "issues": issues,
        "score": round(adjusted_score),
        "percentile": round(percentile, 1),
        "top_percentage": top_percentage,
        "tier": tier
    }

def generate_svg(m):
    svg = f"""<svg width="495" height="205" viewBox="0 0 495 205" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 17px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .subtitle {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #7970a9; }}
    .stat-label {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .stat-val {{ font: 700 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .rank-text {{ font: 700 32px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d847; }}
    .rank-sub {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
  </style>
  <rect width="495" height="205" rx="10" fill="#141321" stroke="#fe428e" stroke-width="1"/>
  
  <text x="25" y="32" class="header">GitHub Standing (Active Developer Index)</text>
  <text x="25" y="48" class="subtitle">AI-era weighted: human review, PR shipping, and org collaboration</text>
  
  <text x="25" y="80" class="stat-label">Total Commits (Private &amp; Org):</text>
  <text x="260" y="80" class="stat-val">{m['commits']:,}</text>
  
  <text x="25" y="105" class="stat-label">Pull Requests Merged/Open:</text>
  <text x="260" y="105" class="stat-val">{m['prs']:,}</text>
  
  <text x="25" y="130" class="stat-label">Code Reviews Given:</text>
  <text x="260" y="130" class="stat-val">{m['reviews']:,}</text>
  
  <text x="25" y="155" class="stat-label">Issues Triaged &amp; Opened:</text>
  <text x="260" y="155" class="stat-val">{m['issues']:,}</text>

  <text x="25" y="180" class="stat-label">Percentile (vs. Active Developers):</text>
  <text x="260" y="180" class="stat-val">{m['percentile']}%</text>

  <!-- Circular Tier Badge -->
  <circle cx="410" cy="100" r="45" stroke="#fe428e" stroke-width="3" fill="#1a1829"/>
  <text x="410" y="110" text-anchor="middle" class="rank-text">{m['tier']}</text>
  <text x="410" y="165" text-anchor="middle" class="rank-sub">Top {m['top_percentage']}%</text>
</svg>"""
    with open("percentile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    data = fetch_data()
    metrics = compute_ai_era_percentile(data)
    generate_svg(metrics)
    print(f"Computed Rank: Top {metrics['top_percentage']}% | Tier: {metrics['tier']} | Score: {metrics['score']}")
