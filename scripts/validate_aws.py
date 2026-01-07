#!/usr/bin/env python3
"""
Validate AWS prerequisites for portfolio-github-management.

This script checks:
1. AWS credentials are configured and valid
2. CloudFormation stack is deployed
3. S3 bucket exists and is accessible
4. IAM role exists with correct trust policy
5. OIDC provider is configured
"""

import argparse
import json
import sys
from typing import NamedTuple

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("Error: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


class ValidationResult(NamedTuple):
    """Result of a validation check."""

    passed: bool
    message: str
    details: str | None = None


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")


def print_result(name: str, result: ValidationResult) -> None:
    """Print a validation result."""
    status = (
        f"{Colors.GREEN}PASS{Colors.RESET}"
        if result.passed
        else f"{Colors.RED}FAIL{Colors.RESET}"
    )
    print(f"\n  [{status}] {name}")
    print(f"         {result.message}")
    if result.details:
        for line in result.details.split("\n"):
            print(f"         {Colors.YELLOW}{line}{Colors.RESET}")


def get_session(profile: str | None, region: str) -> boto3.Session:
    """Create a boto3 session with optional profile."""
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def validate_aws_credentials(session: boto3.Session) -> ValidationResult:
    """Validate AWS credentials are configured and working."""
    try:
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return ValidationResult(
            passed=True,
            message="AWS credentials are valid",
            details=f"Account: {identity['Account']}\nARN: {identity['Arn']}",
        )
    except NoCredentialsError:
        return ValidationResult(
            passed=False,
            message="No AWS credentials found",
            details="Configure credentials via environment variables, ~/.aws/credentials, or IAM role",
        )
    except ClientError as e:
        return ValidationResult(
            passed=False,
            message="AWS credentials are invalid",
            details=str(e),
        )


def validate_cloudformation_stack(
    session: boto3.Session, stack_name: str
) -> ValidationResult:
    """Validate CloudFormation stack exists and is deployed."""
    try:
        cfn = session.client("cloudformation")
        response = cfn.describe_stacks(StackName=stack_name)
        stack = response["Stacks"][0]
        status = stack["StackStatus"]

        if status in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
            details = "\n".join(f"{k}: {v}" for k, v in outputs.items())
            return ValidationResult(
                passed=True,
                message=f"Stack '{stack_name}' is deployed (status: {status})",
                details=details if details else None,
            )
        else:
            return ValidationResult(
                passed=False,
                message=f"Stack '{stack_name}' is in unexpected state: {status}",
                details="Stack should be in CREATE_COMPLETE or UPDATE_COMPLETE state",
            )
    except ClientError as e:
        if "does not exist" in str(e):
            return ValidationResult(
                passed=False,
                message=f"Stack '{stack_name}' does not exist",
                details="Deploy the stack with:\n"
                "aws cloudformation deploy \\\n"
                "  --template-file cloudformation/github-oidc-terraform-state.yaml \\\n"
                f"  --stack-name {stack_name} \\\n"
                "  --capabilities CAPABILITY_NAMED_IAM",
            )
        return ValidationResult(passed=False, message="Error checking stack", details=str(e))


def validate_s3_bucket(session: boto3.Session, bucket_name: str) -> ValidationResult:
    """Validate S3 bucket exists and is accessible."""
    try:
        s3 = session.client("s3")

        # Check bucket exists
        s3.head_bucket(Bucket=bucket_name)

        # Check versioning
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        versioning_status = versioning.get("Status", "Disabled")

        # Check encryption
        try:
            encryption = s3.get_bucket_encryption(Bucket=bucket_name)
            encryption_status = "Enabled"
        except ClientError:
            encryption_status = "Disabled"

        # Check public access block
        try:
            public_access = s3.get_public_access_block(Bucket=bucket_name)
            config = public_access["PublicAccessBlockConfiguration"]
            public_blocked = all([
                config.get("BlockPublicAcls", False),
                config.get("BlockPublicPolicy", False),
                config.get("IgnorePublicAcls", False),
                config.get("RestrictPublicBuckets", False),
            ])
        except ClientError:
            public_blocked = False

        details = (
            f"Versioning: {versioning_status}\n"
            f"Encryption: {encryption_status}\n"
            f"Public Access Blocked: {public_blocked}"
        )

        if versioning_status == "Enabled" and encryption_status == "Enabled" and public_blocked:
            return ValidationResult(
                passed=True,
                message=f"Bucket '{bucket_name}' is properly configured",
                details=details,
            )
        else:
            return ValidationResult(
                passed=False,
                message=f"Bucket '{bucket_name}' exists but may not be properly configured",
                details=details,
            )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            return ValidationResult(
                passed=False,
                message=f"Bucket '{bucket_name}' does not exist",
                details="Deploy the CloudFormation stack to create the bucket",
            )
        elif error_code == "403":
            return ValidationResult(
                passed=False,
                message=f"Access denied to bucket '{bucket_name}'",
                details="Check IAM permissions for s3:HeadBucket",
            )
        return ValidationResult(passed=False, message="Error checking bucket", details=str(e))


def validate_iam_role(session: boto3.Session, role_name: str, github_org: str, github_repo: str) -> ValidationResult:
    """Validate IAM role exists with correct trust policy."""
    try:
        iam = session.client("iam")
        role = iam.get_role(RoleName=role_name)
        trust_policy = role["Role"]["AssumeRolePolicyDocument"]

        # Check for OIDC federation
        statements = trust_policy.get("Statement", [])
        has_oidc = False
        correct_repo = False

        for stmt in statements:
            principal = stmt.get("Principal", {})
            federated = principal.get("Federated", "")
            if "token.actions.githubusercontent.com" in federated:
                has_oidc = True
                # Check condition for repo
                conditions = stmt.get("Condition", {})
                string_like = conditions.get("StringLike", {})
                sub_condition = string_like.get("token.actions.githubusercontent.com:sub", "")
                if f"repo:{github_org}/{github_repo}:" in sub_condition:
                    correct_repo = True

        if has_oidc and correct_repo:
            return ValidationResult(
                passed=True,
                message=f"Role '{role_name}' is properly configured",
                details=f"Trust policy allows: {github_org}/{github_repo}",
            )
        elif has_oidc:
            return ValidationResult(
                passed=False,
                message=f"Role '{role_name}' exists but trust policy may be incorrect",
                details=f"Expected repo: {github_org}/{github_repo}",
            )
        else:
            return ValidationResult(
                passed=False,
                message=f"Role '{role_name}' does not have OIDC trust policy",
                details="Role should trust token.actions.githubusercontent.com",
            )

    except ClientError as e:
        if "NoSuchEntity" in str(e):
            return ValidationResult(
                passed=False,
                message=f"Role '{role_name}' does not exist",
                details="Deploy the CloudFormation stack to create the role",
            )
        return ValidationResult(passed=False, message="Error checking role", details=str(e))


def validate_oidc_provider(session: boto3.Session) -> ValidationResult:
    """Validate GitHub OIDC provider exists."""
    try:
        iam = session.client("iam")
        providers = iam.list_open_id_connect_providers()

        github_provider = None
        for provider in providers.get("OpenIDConnectProviderList", []):
            arn = provider["Arn"]
            if "token.actions.githubusercontent.com" in arn:
                github_provider = arn
                break

        if github_provider:
            # Get provider details
            details_response = iam.get_open_id_connect_provider(
                OpenIDConnectProviderArn=github_provider
            )
            audiences = details_response.get("ClientIDList", [])
            return ValidationResult(
                passed=True,
                message="GitHub OIDC provider is configured",
                details=f"ARN: {github_provider}\nAudiences: {', '.join(audiences)}",
            )
        else:
            return ValidationResult(
                passed=False,
                message="GitHub OIDC provider not found",
                details="Deploy the CloudFormation stack to create the OIDC provider",
            )

    except ClientError as e:
        return ValidationResult(
            passed=False, message="Error checking OIDC provider", details=str(e)
        )


def main() -> int:
    """Run all validations and return exit code."""
    parser = argparse.ArgumentParser(
        description="Validate AWS prerequisites for portfolio-github-management"
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (required if no default profile is set)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--stack-name",
        default="github-terraform-state",
        help="CloudFormation stack name (default: github-terraform-state)",
    )
    parser.add_argument(
        "--bucket-name",
        default="williambrady-terraform-state-918573727633",
        help="S3 bucket name (default: williambrady-terraform-state-918573727633)",
    )
    parser.add_argument(
        "--role-name",
        default="github-actions-portfolio-github-management",
        help="IAM role name (default: github-actions-portfolio-github-management)",
    )
    parser.add_argument(
        "--github-org",
        default="williambrady",
        help="GitHub organization/user (default: williambrady)",
    )
    parser.add_argument(
        "--github-repo",
        default="portfolio-github-management",
        help="GitHub repository name (default: portfolio-github-management)",
    )
    args = parser.parse_args()

    print_header("AWS Prerequisites Validation")
    print(f"\n  Profile: {args.profile or '(default)'}")
    print(f"  Region:  {args.region}")
    print(f"  Stack:   {args.stack_name}")
    print(f"  Bucket:  {args.bucket_name}")
    print(f"  Role:    {args.role_name}")
    print(f"  Repo:    {args.github_org}/{args.github_repo}")

    # Create session with profile
    try:
        session = get_session(args.profile, args.region)
    except Exception as e:
        print(f"\n{Colors.RED}Failed to create AWS session: {e}{Colors.RESET}")
        if args.profile:
            print(f"Check that profile '{args.profile}' exists in ~/.aws/credentials or ~/.aws/config")
        return 1

    results: list[tuple[str, ValidationResult]] = []

    # Run validations
    print_header("1. AWS Credentials")
    result = validate_aws_credentials(session)
    results.append(("AWS Credentials", result))
    print_result("AWS Credentials", result)

    # Only continue if credentials are valid
    if not result.passed:
        print(f"\n{Colors.RED}Validation failed: Fix AWS credentials before continuing{Colors.RESET}")
        return 1

    print_header("2. CloudFormation Stack")
    result = validate_cloudformation_stack(session, args.stack_name)
    results.append(("CloudFormation Stack", result))
    print_result("CloudFormation Stack", result)

    print_header("3. S3 Bucket")
    result = validate_s3_bucket(session, args.bucket_name)
    results.append(("S3 Bucket", result))
    print_result("S3 Bucket", result)

    print_header("4. IAM Role")
    result = validate_iam_role(
        session, args.role_name, args.github_org, args.github_repo
    )
    results.append(("IAM Role", result))
    print_result("IAM Role", result)

    print_header("5. OIDC Provider")
    result = validate_oidc_provider(session)
    results.append(("OIDC Provider", result))
    print_result("OIDC Provider", result)

    # Summary
    print_header("Summary")
    passed = sum(1 for _, r in results if r.passed)
    total = len(results)

    for name, result in results:
        status = (
            f"{Colors.GREEN}PASS{Colors.RESET}"
            if result.passed
            else f"{Colors.RED}FAIL{Colors.RESET}"
        )
        print(f"  [{status}] {name}")

    print()
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}All validations passed! ({passed}/{total}){Colors.RESET}")
        print("\nYou can now run:")
        print("  cd terraform && terraform init && terraform plan")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}Some validations failed ({passed}/{total}){Colors.RESET}")
        print("\nFix the issues above before running Terraform.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
