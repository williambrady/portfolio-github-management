output "repositories" {
  description = "Map of managed repositories"
  value = {
    for name, repo in github_repository.managed : name => {
      id        = repo.id
      node_id   = repo.node_id
      full_name = repo.full_name
      html_url  = repo.html_url
      ssh_url   = repo.ssh_clone_url
      http_url  = repo.http_clone_url
    }
  }
}

output "repository_names" {
  description = "List of managed repository names"
  value       = keys(github_repository.managed)
}

