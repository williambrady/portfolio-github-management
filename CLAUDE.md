# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infrastructure as Code project for managing GitHub repositories using Terraform, with AWS prerequisites (OIDC, S3 state backend) managed via CloudFormation.

## Common Commands

### Pre-commit Hooks
```bash
# Install hooks (first time setup)
pip install pre-commit
pre-commit install

# Run all checks manually
pre-commit run --all-files
```

### Terraform (from terraform/ directory)
```bash
cd terraform
export TF_VAR_github_token="your-github-pat"
export AWS_PROFILE=your-profile

terraform init              # Initialize backend
terraform fmt -recursive    # Format all files
terraform validate          # Validate configuration
terraform plan              # Preview changes
terraform apply             # Apply changes
```

### AWS Infrastructure Validation
```bash
pip install -r scripts/requirements.txt
python scripts/validate_aws.py --profile your-profile
```

### CloudFormation Deployment
```bash
aws cloudformation deploy \
  --template-file cloudformation/github-oidc-terraform-state.yaml \
  --stack-name github-terraform-state \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Architecture

### Configuration-Driven Repository Management

The project uses a YAML configuration pattern where `repositories.yaml` (at project root) defines:
- **defaults**: Base settings applied to all repositories
- **repositories**: Per-repo overrides that merge with defaults

This is processed in `terraform/locals.tf` using `yamldecode()` and map merging, then consumed by `for_each` loops in `main.tf`.

### Key Terraform Resources

- `github_repository.managed` - Creates/manages repos with 28+ configuration options
- `github_branch_protection.main` - Conditionally applied when `branch_protection_enabled: true`

### AWS Prerequisites (CloudFormation)

`cloudformation/github-oidc-terraform-state.yaml` creates:
- GitHub OIDC Provider for keyless authentication
- S3 bucket with versioning/encryption for Terraform state
- IAM role scoped to this specific repo via OIDC trust policy

### CI/CD Flow

- **Push to main**: `terraform apply` (auto-approved)
- **Push to develop**: `terraform plan` only
- **PRs**: `terraform plan` with results posted as PR comment

## Adding New Repositories

Edit `repositories.yaml`:
```yaml
repositories:
  new-repo-name:
    description: "My new repository"
    visibility: public  # Override default (private)
    # Other settings inherit from defaults section
```

## Pre-commit Hooks

The project enforces code quality via pre-commit hooks:
- `terraform_fmt`, `terraform_validate`, `terraform_tflint` - Terraform checks
- `terraform_docs` - Auto-generates README documentation
- `terraform-plan` (local) - Runs plan before commit on .tf file changes
- Standard checks: trailing-whitespace, end-of-file-fixer, check-yaml

## Required Secrets (GitHub Actions)

- `AWS_ACCOUNT_ID` - 12-digit AWS account number
- `GH_APP_ID` - GitHub App ID (from app settings page)
- `GH_APP_PRIVATE_KEY` - GitHub App private key (.pem file contents)
