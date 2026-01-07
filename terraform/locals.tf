# Load and parse the YAML configuration file
locals {
  config = yamldecode(file(var.config_file))

  # Extract defaults from config
  defaults = local.config.defaults

  # Build repository configurations by merging defaults with overrides
  repositories = {
    for repo in local.config.repositories : repo.name => merge(
      local.defaults,
      repo
    )
  }

  # Flatten collaborators for all repositories
  # Creates a map with key "repo_name:username" for each collaborator
  repository_collaborators = merge([
    for repo_name, repo in local.repositories : {
      for collab in lookup(repo, "collaborators", []) :
      "${repo_name}:${collab.username}" => {
        repository = repo_name
        username   = collab.username
        permission = collab.permission
      }
    }
  ]...)

}

