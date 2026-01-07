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
}

