# GitHub Repository Management
# Creates and manages repositories based on repositories.yaml

resource "github_repository" "managed" {
  for_each = local.repositories

  name        = each.key
  description = lookup(each.value, "description", null)
  visibility  = lookup(each.value, "visibility", "private")

  # Repository features
  has_issues      = lookup(each.value, "has_issues", true)
  has_discussions = lookup(each.value, "has_discussions", false)
  has_projects    = lookup(each.value, "has_projects", true)
  has_wiki        = lookup(each.value, "has_wiki", true)
  has_downloads   = lookup(each.value, "has_downloads", true)

  # Repository settings
  is_template                 = lookup(each.value, "is_template", false)
  allow_merge_commit          = lookup(each.value, "allow_merge_commit", true)
  allow_squash_merge          = lookup(each.value, "allow_squash_merge", true)
  allow_rebase_merge          = lookup(each.value, "allow_rebase_merge", true)
  allow_auto_merge            = lookup(each.value, "allow_auto_merge", false)
  delete_branch_on_merge      = lookup(each.value, "delete_branch_on_merge", false)
  allow_update_branch         = lookup(each.value, "allow_update_branch", false)
  squash_merge_commit_title   = lookup(each.value, "squash_merge_commit_title", "COMMIT_OR_PR_TITLE")
  squash_merge_commit_message = lookup(each.value, "squash_merge_commit_message", "COMMIT_MESSAGES")
  merge_commit_title          = lookup(each.value, "merge_commit_title", "MERGE_MESSAGE")
  merge_commit_message        = lookup(each.value, "merge_commit_message", "PR_TITLE")

  # Security settings
  vulnerability_alerts = lookup(each.value, "vulnerability_alerts", true)

  # Archive settings
  archived = lookup(each.value, "archived", false)

  # Auto-init with README
  auto_init = lookup(each.value, "auto_init", true)

  # Topics/tags
  topics = lookup(each.value, "topics", [])

  # Homepage URL
  homepage_url = lookup(each.value, "homepage_url", null)

  # Gitignore and license templates (only for new repos)
  gitignore_template = lookup(each.value, "gitignore_template", null)
  license_template   = lookup(each.value, "license_template", null)

  lifecycle {
    ignore_changes = [
      # Ignore changes to auto_init after creation
      auto_init,
      gitignore_template,
      license_template,
    ]
  }
}

# Branch protection rules
resource "github_branch_protection" "main" {
  for_each = {
    for name, repo in local.repositories : name => repo
    if lookup(repo, "branch_protection_enabled", false)
  }

  repository_id = github_repository.managed[each.key].node_id
  pattern       = lookup(each.value, "default_branch", "main")

  # Require pull request reviews
  required_pull_request_reviews {
    dismiss_stale_reviews           = lookup(each.value, "dismiss_stale_reviews", true)
    require_code_owner_reviews      = lookup(each.value, "require_code_owner_reviews", false)
    required_approving_review_count = lookup(each.value, "required_approving_review_count", 1)
  }

  # Require status checks
  required_status_checks {
    strict   = lookup(each.value, "require_branches_up_to_date", true)
    contexts = lookup(each.value, "required_status_checks", [])
  }

  # Enforce on admins
  enforce_admins = lookup(each.value, "enforce_admins", false)

  # Allow force pushes
  allows_force_pushes = lookup(each.value, "allows_force_pushes", false)

  # Allow deletions
  allows_deletions = lookup(each.value, "allows_deletions", false)

  # Require conversation resolution
  require_conversation_resolution = lookup(each.value, "require_conversation_resolution", true)
}

# Repository collaborators
resource "github_repository_collaborator" "managed" {
  for_each = local.repository_collaborators

  repository = github_repository.managed[each.value.repository].name
  username   = each.value.username
  permission = each.value.permission
}

# CODEOWNERS files
resource "github_repository_file" "codeowners" {
  for_each = local.repositories_with_codeowners

  repository          = github_repository.managed[each.key].name
  branch              = lookup(each.value, "default_branch", "main")
  file                = ".github/CODEOWNERS"
  content             = each.value.codeowners
  commit_message      = "Manage CODEOWNERS via Terraform"
  overwrite_on_create = true
}

