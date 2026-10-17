# Deploy to AWS: quickstart

A copy-paste runbook for deploying the whole stack (API on EC2 behind CloudFront, console on Amplify). For the design, operations, costs and troubleshooting, see [infra/README.md](infra/README.md).

**Run it from:** AWS CloudShell (nothing to install), or any machine with AWS CLI v2 (`aws configure` done, admin-level access), `git`, `python3` and `curl`. Use bash; on Windows, use Git Bash or WSL.

**You need:** a GitHub personal access token with read access to this repo (classic token: `repo` scope).

Total time is about 25 minutes, most of it waiting.

---

## 0. Settings

```bash
export AWS_REGION=ap-south-1          # pick one region and keep it
export AWS_DEFAULT_REGION=$AWS_REGION
export PROJECT=svo ENV=prod
export BRANCH=feature/frontend        # the branch that holds infra/ and app/client
read -s GITHUB_TOKEN; export GITHUB_TOKEN   # paste the token; nothing is echoed

git clone --branch "$BRANCH" "https://$GITHUB_TOKEN@github.com/Dilhara11/ScamFit-TnsorForge-Lumora.git" svo-deploy
cd svo-deploy
```

## 1. Build the API image in AWS (~10 min)

```bash
aws cloudformation deploy --stack-name $PROJECT-ecr \
  --template-file infra/cloudformation/01-ecr.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectName=$PROJECT BranchName=$BRANCH GitHubAccessToken="$GITHUB_TOKEN"

BUILD=$(aws codebuild start-build --project-name $PROJECT-api-image --query build.id --output text)
while S=$(aws codebuild batch-get-builds --ids "$BUILD" --query 'builds[0].buildStatus' --output text); [ "$S" = IN_PROGRESS ]; do echo building...; sleep 30; done; echo "$S"
```

The last line must print `SUCCEEDED` before you continue.
- If the stack fails with a source-credential error, GitHub is already connected for CodeBuild in this region. Rerun the deploy with `GitHubAccessToken=""`.
- If the build fails with `toomanyrequests`, Docker Hub is rate-limiting. See Troubleshooting in [infra/README.md](infra/README.md).

## 2. Create the API keys

```bash
CREDS=$(python3 -c 'import json, secrets; print(json.dumps({"analyst-1": secrets.token_urlsafe(36)}))')
aws ssm put-parameter --name /$PROJECT/$ENV/credentials-json --type SecureString --value "$CREDS"
echo "$CREDS"   # save analyst-1's key somewhere private; you need it in step 5
```

## 3. Start the server (~8 min)

```bash
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SUBNET=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
PL=$(aws ec2 describe-managed-prefix-lists --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing --query 'PrefixLists[0].PrefixListId' --output text)

aws cloudformation deploy --stack-name $PROJECT-$ENV-server \
  --template-file infra/cloudformation/02-server.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectName=$PROJECT EnvName=$ENV VpcId=$VPC SubnetId=$SUBNET CloudFrontPrefixListId=$PL

out() { aws cloudformation describe-stacks --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text; }
API_URL=$(out $PROJECT-$ENV-server ApiUrl); INSTANCE=$(out $PROJECT-$ENV-server InstanceId)
echo "$API_URL"; curl -fsS "$API_URL/health/ready"   # may 403/502 for a few minutes while CloudFront propagates
```

If `VPC` prints `None`, the account has no default VPC. Set `VPC` and `SUBNET` by hand to a VPC and one of its **public** subnets.

## 4. Deploy the console (~5 min)

```bash
aws cloudformation deploy --stack-name $PROJECT-$ENV-client \
  --template-file infra/cloudformation/03-client.yaml \
  --parameter-overrides ProjectName=$PROJECT EnvName=$ENV BranchName=$BRANCH GitHubAccessToken="$GITHUB_TOKEN" ApiUrl=$API_URL

APP_ID=$(out $PROJECT-$ENV-client AppId)
aws amplify start-job --app-id $APP_ID --branch-name $BRANCH --job-type RELEASE
```

## 5. Connect the two and test

```bash
# The API picks up the console origin (CORS) on restart.
aws ssm send-command --instance-ids $INSTANCE --document-name AWS-RunShellScript --parameters commands="systemctl restart svo-api"
out $PROJECT-$ENV-client ConsoleUrl
```

Wait until the Amplify build shows **Deployed** (Amplify console → the app → branch). Then open the console URL, enter `analyst-1`'s key in the connection settings, and submit a test message.

---

## Later

| To | Run |
| --- | --- |
| Ship client changes | `git push`; Amplify rebuilds by itself |
| Ship API changes | `git push`, then step 1's `start-build` and step 5's restart |
| Roll the API back | Redeploy step 3 adding `ImageTag=<12-char sha from ECR>`, then restart |
| Read API logs | CloudWatch → log group `/svo/prod/api` |
| Get a shell on the server | `aws ssm start-session --target $INSTANCE` |
| Tear everything down | Delete stacks `svo-prod-client`, `svo-prod-server`, `svo-ecr` in that order |

Opening a new terminal later? Rerun section 0's `export` lines and the `out`, `API_URL`, `INSTANCE` lines from step 3.
