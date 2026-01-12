# portfolio-github-management

GitHub repository management via Terraform.

This project manages GitHub repositories under [github.com/williambrady](https://github.com/williambrady) using Infrastructure as Code. Repositories are defined in a YAML configuration file with sensible defaults and per-repository overrides.

## Prerequisites

Before using this repository, you must deploy the AWS infrastructure for Terraform state management and GitHub Actions authentication.

### 1. Deploy the CloudFormation Stack

The CloudFormation template creates:
- **GitHub OIDC Provider** - Enables secure, credential-free authentication from GitHub Actions
- **S3 Bucket** - Stores Terraform state with encryption and versioning
- **IAM Role** - Grants GitHub Actions access to the S3 bucket via OIDC trust policy

#### Deploy via AWS CLI

```bash
# Deploy with default parameters
aws cloudformation deploy \
  --template-file cloudformation/github-oidc-terraform-state.yaml \
  --stack-name github-terraform-state \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --profile portfolio

# Or customize parameters
aws cloudformation deploy \
  --template-file cloudformation/github-oidc-terraform-state.yaml \
  --stack-name github-terraform-state \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --parameter-overrides \
    GitHubOrg=williambrady \
    GitHubRepo=portfolio-github-management \
    StateBucketName=williambrady-terraform-state-918573727633
```

#### View Stack Outputs

After deployment, retrieve the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name github-terraform-state \
  --query 'Stacks[0].Outputs' \
  --output table
```

#### Validate Deployment

Run the validation script to verify all prerequisites are correctly configured:

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Run validation
python scripts/validate_aws.py
```

The script validates:
- AWS credentials are configured and valid
- CloudFormation stack is deployed successfully
- S3 bucket exists with proper encryption and versioning
- IAM role exists with correct OIDC trust policy
- GitHub OIDC provider is configured

You can customize the validation with arguments:

```bash
python scripts/validate_aws.py \
  --profile my-aws-profile \
  --region us-east-1 \
  --stack-name github-terraform-state \
  --bucket-name williambrady-terraform-state-918573727633 \
  --role-name github-actions-portfolio-github-management \
  --github-org williambrady \
  --github-repo portfolio-github-management
```

**Note:** The `--profile` argument is required if you don't have a default AWS profile configured.

### 2. Create a GitHub App

A GitHub App provides secure, short-lived tokens for Terraform to manage repositories. This is more secure than a Personal Access Token.

#### Create the App

1. Go to **GitHub Settings** > **Developer settings** > **GitHub Apps** > **New GitHub App**
2. Fill in the basics:
   - **GitHub App name**: `portfolio-terraform` (or any unique name)
   - **Homepage URL**: `https://github.com/williambrady/portfolio-github-management`
3. Uncheck **Webhook** > **Active** (not needed)
4. Set **Repository permissions**:
   | Permission | Access |
   |------------|--------|
   | Administration | Read and write |
   | Contents | Read and write |
   | Metadata | Read-only |
5. Under "Where can this GitHub App be installed?", select **Only on this account**
6. Click **Create GitHub App**

#### Generate a Private Key

1. On the app's settings page, note the **App ID** (you'll need this)
2. Scroll to **Private keys** and click **Generate a private key**
3. Save the downloaded `.pem` file securely

#### Install the App

1. Click **Install App** in the left sidebar
2. Select your account and click **Install**
3. Choose **All repositories** and confirm

### 3. Configure GitHub Repository Secrets

Add the following secrets to your GitHub repository:

| Secret | Description |
|--------|-------------|
| `AWS_ACCOUNT_ID` | Your AWS account ID (12-digit number) |
| `GH_APP_ID` | The App ID from the GitHub App settings page |
| `GH_APP_PRIVATE_KEY` | The entire contents of the `.pem` file |

To add secrets:
1. Go to your repository on GitHub
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret** for each secret

### 4. Initialize Terraform Locally (Optional)

For local development:

```bash
cd terraform

# Export your GitHub token
export TF_VAR_github_token="your-github-pat"

# Configure AWS credentials (or use AWS SSO/profiles)
export AWS_PROFILE=your-profile

# Initialize Terraform
terraform init

# Verify configuration
terraform plan
```

## Branching Strategy

```
main (production)
 └── develop (integration)
      └── feature/* (new features)
```

| Branch | Purpose | Merges To |
|--------|---------|-----------|
| `main` | Production. Terraform apply runs on push. | - |
| `develop` | Integration branch. Terraform plan runs on push. | `main` (via PR) |
| `feature/*` | New features. | `develop` (via PR) |

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── terraform.yml    # CI/CD workflow
├── cloudformation/
│   └── github-oidc-terraform-state.yaml  # AWS prerequisites
├── scripts/
│   ├── requirements.txt     # Python dependencies
│   └── validate_aws.py      # AWS validation script
├── terraform/
│   ├── backend.tf           # S3 state backend configuration
│   ├── locals.tf            # Configuration parsing
│   ├── main.tf              # GitHub resources
│   ├── outputs.tf           # Output definitions
│   ├── providers.tf         # Provider configuration
│   ├── variables.tf         # Input variables
│   └── versions.tf          # Version constraints
├── .pre-commit-config.yaml  # Pre-commit hooks
├── .terraform-docs.yml      # Terraform docs config
├── repositories.yaml        # Repository definitions
└── README.md
```

## Usage

### Adding a New Repository

> **Note**: This project uses an **import-only model**. GitHub Apps cannot create repositories in personal accounts - they can only manage existing repositories. You must create the repository manually first, then import it into Terraform.

#### Step 1: Create the Repository on GitHub

1. Go to [github.com/new](https://github.com/new)
2. Create the repository with basic settings (name, visibility)
3. Note: Other settings will be managed by Terraform after import

#### Step 2: Add to Configuration

Edit `repositories.yaml`:

```yaml
repositories:
  - name: my-new-repo
    description: "Description of my repository"
    visibility: public
    topics:
      - topic1
      - topic2
    has_issues: true
    has_wiki: false
```

#### Step 3: Import into Terraform

```bash
cd terraform
terraform import 'github_repository.managed["my-new-repo"]' my-new-repo
```

#### Step 4: Apply Configuration

```bash
terraform plan   # Verify changes look correct
terraform apply  # Apply the configuration
```

Commit and push your changes to `repositories.yaml`.

### Configuration Options

All options have defaults defined in `repositories.yaml`. Override any setting per-repository:

| Option | Default | Description |
|--------|---------|-------------|
| `visibility` | `private` | `public`, `private`, or `internal` |
| `has_issues` | `true` | Enable issues |
| `has_wiki` | `true` | Enable wiki |
| `has_projects` | `true` | Enable projects |
| `has_discussions` | `false` | Enable discussions |
| `allow_merge_commit` | `true` | Allow merge commits |
| `allow_squash_merge` | `true` | Allow squash merging |
| `allow_rebase_merge` | `true` | Allow rebase merging |
| `delete_branch_on_merge` | `true` | Auto-delete head branches |
| `vulnerability_alerts` | `true` | Enable Dependabot alerts |
| `branch_protection_enabled` | `false` | Enable branch protection on default branch |

See `repositories.yaml` for the complete list of options.

### Removing a Repository from Management

To stop managing a repository without deleting it:

1. Remove the repository from `repositories.yaml`
2. Remove from Terraform state (does not delete the actual repo):
   ```bash
   cd terraform
   terraform state rm 'github_repository.managed["repo-name"]'
   ```
3. Commit and push

> **Note**: The `prevent_destroy` lifecycle rule protects repositories from accidental deletion. If you truly need to delete a repository, you must do so manually via the GitHub UI after removing it from Terraform state.

## CI/CD Workflow

The GitHub Actions workflow:

| Event | Action |
|-------|--------|
| Push to `develop` | Terraform plan (validate changes) |
| PR to `develop` or `main` | Terraform plan with PR comment |
| Push to `main` | Terraform apply (deploy changes) |

### Security

- **No long-lived credentials** - Uses OIDC for AWS authentication
- **Least privilege** - IAM role only has access to the state bucket
- **State encryption** - S3 bucket uses AES-256 encryption
- **State locking** - Uses S3-native locking (Terraform 1.10+)

## Local Development

### Pre-commit Hooks

Install pre-commit hooks for local validation:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks include:
- `terraform fmt` - Format check
- `terraform validate` - Configuration validation
- `terraform-docs` - Documentation generation
- `tflint` - Linting

## License

MIT
