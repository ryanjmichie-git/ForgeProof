# Modify CI/CD pipeline to add deployment stage

## Description
Add a production deployment stage to the GitLab CI/CD pipeline that auto-deploys to AWS on merge to main.

## Acceptance Criteria
- Add a `deploy` stage to `.gitlab-ci.yml`
- Configure AWS credentials via environment variables
- Deploy using `aws ecs update-service`
- Add rollback capability on failure

## Suggested Files
- `.gitlab-ci.yml` — modify pipeline configuration
- `scripts/deploy.sh` — deployment script
- `.env.production` — production environment config
