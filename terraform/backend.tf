terraform {
  backend "s3" {
    bucket       = "williambrady-terraform-state-918573727633"
    key          = "portfolio-github-management/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
