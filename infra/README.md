# AWS deployment

Infrastructure as code for running the Scam Variant Observatory on AWS. It uses three CloudFormation stacks, deployed in order from **AWS CloudShell**, so the deploying machine needs no local AWS credentials, Docker or bandwidth.

| File | Creates |
| --- | --- |
| `cloudformation/01-ecr.yaml` | ECR repository `svo-api` and the CodeBuild project that builds the API image inside AWS |
| `buildspec.yml` | CodeBuild steps: build `app/server/Dockerfile`, smoke-test `/health/ready`, push `<sha>` and `latest` |
| `cloudformation/02-server.yaml` | EC2 instance (systemd + Docker), encrypted EBS data volume with daily snapshots, Elastic IP, CloudFront HTTPS endpoint |
| `cloudformation/03-client.yaml` | Amplify Hosting app that builds `app/client` on every push, and the SSM parameter with the console origin, which the API uses for CORS |

## Architecture

```
 GitHub ──push──▶ Amplify (builds app/client) ──▶ https://<branch>.<id>.amplifyapp.com
    │                                                      │ browser fetch, X-API-Key
    └──start-build──▶ CodeBuild ──push──▶ ECR              ▼
                                           │      CloudFront (HTTPS, no caching)
                                           │ pull          │ HTTP :8000, CloudFront IPs only
                                           ▼               ▼
                                   EC2 t3.medium ── svo-api container ── /srv/svo-data (EBS, SQLite)
                                           ▲
                         SSM Parameter Store /svo/<env>/{credentials-json, allowed-origins, image-tag}
```

Design choices and why:

- **One instance, no autoscaling.** The API keeps its state in SQLite and runs one uvicorn worker. Running two instances would split the database. To scale up, change `InstanceType`.
- **The data lives on its own EBS volume.** If the instance is replaced, the database is kept. If the stack is deleted, the volume is snapshotted, and DLM takes a snapshot every day (7 kept).
- **CloudFront supplies the TLS.** Amplify serves HTTPS, so the browser blocks plain-HTTP API calls. CloudFront provides an HTTPS URL without needing a domain or a certificate. The security group accepts port 8000 only from CloudFront's origin-facing IP ranges.
- **Always `SVO_MODE=authenticated`.** The server README forbids exposing `local_demo`. Keys live in an SSM SecureString, not in templates or images.
- **No SSH.** Shell access goes through Session Manager, IMDSv2 is required, and the container keeps the same hardening as `compose.yaml` (read-only root filesystem, `cap_drop ALL`, 2 vCPU / 2 GB limit).

## Should the image be built in AWS?

Yes, though not because the model is heavy. The bundle is `intfloat/multilingual-e5-small`: 118M parameters, about 450 MB of weights, running on CPU with `torch+cpu`. It needs no GPU, SageMaker or separate model store, and a `t3.medium` (2 vCPU, 4 GB) serves it inside the 2 GB container limit used locally.

The build is heavy in other ways:

- The finished image is about 2 GB (torch, the encoder and Python). Pushing that from a home connection on every change is slow, and this device has no AWS credentials anyway.
- Git cannot hold the weights (the GitHub limit is 100 MB). The Dockerfile already restores them from Hugging Face at the pinned revision and checks them against the manifest hash. CodeBuild can therefore build from a plain `git clone` and downloads at AWS speeds.
- Each build runs on a fresh machine from the committed source only, so it is reproducible.

A `BUILD_GENERAL1_MEDIUM` build takes roughly 8–12 minutes and costs about $0.10 (the layer cache speeds up repeats). If the Hugging Face dependency becomes a concern, mirror the weights to S3 and fetch them from there instead. That is a later improvement, not a blocker.

## Prerequisites

1. **Commit and push everything the build needs.** CodeBuild and Amplify build from GitHub, not from this machine. At minimum `app/client/`, `app/server/scripts/fetch_model_weights.py`, `training/src/svo/v2.py`, `training/runs/v2/candidates/e5_tfidf/bundle/` (without `model.safetensors`, which is gitignored) and `infra/` must be on the branch you deploy.
2. An AWS account where you can create IAM roles, EC2, CloudFront, Amplify, CodeBuild and ECR resources. Administrator access is simplest for the first deployment.
3. A GitHub personal access token with read access to the repository (classic: `repo` scope; fine-grained: Contents and Webhooks read/write). Amplify needs it to install a webhook. CodeBuild needs it only if the repository is private.
4. Pick one region and use it everywhere. Amplify, CodeBuild and EC2 all run there (CloudFront is global).

## First deployment (AWS CloudShell)

Open CloudShell in the chosen region and run the steps in order. Set these variables first:

```bash
export AWS_REGION=ap-south-1          # your region
export PROJECT=svo ENV=prod BRANCH=main
read -s GITHUB_TOKEN                  # paste the token; nothing is echoed
git clone --branch "$BRANCH" "https://$GITHUB_TOKEN@github.com/Dilhara11/ScamFit-TnsorForge-Lumora.git" repo
cd repo
```

### 1. Image pipeline (ECR + CodeBuild)

```bash
aws cloudformation deploy --stack-name $PROJECT-ecr \
  --template-file infra/cloudformation/01-ecr.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectName=$PROJECT BranchName=$BRANCH GitHubAccessToken="$GITHUB_TOKEN"

aws codebuild start-build --project-name $PROJECT-api-image
```

Leave `GitHubAccessToken` out if the repository is public or GitHub is already connected in the CodeBuild console. CodeBuild allows only one GitHub credential per region per account, and the stack fails if one exists already.

Watch the build in **CodeBuild → Build projects → svo-api-image** and wait for it to succeed before step 3. The server pulls `latest` when it boots.

### 2. API keys

Generate one key per analyst. Keys must be unique, ASCII and at least 32 characters:

```bash
CREDS=$(python3 -c 'import json, secrets; print(json.dumps({"analyst-1": secrets.token_urlsafe(36), "analyst-2": secrets.token_urlsafe(36)}))')
aws ssm put-parameter --name /$PROJECT/$ENV/credentials-json --type SecureString --value "$CREDS"
echo "$CREDS"   # hand each analyst their own key over a private channel, then clear the terminal
```

### 3. Server (EC2 + CloudFront)

```bash
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SUBNET=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=default-for-az,Values=true --query 'Subnets[0].SubnetId' --output text)
PL=$(aws ec2 describe-managed-prefix-lists --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing --query 'PrefixLists[0].PrefixListId' --output text)

aws cloudformation deploy --stack-name $PROJECT-$ENV-server \
  --template-file infra/cloudformation/02-server.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectName=$PROJECT EnvName=$ENV VpcId=$VPC SubnetId=$SUBNET CloudFrontPrefixListId=$PL

API_URL=$(aws cloudformation describe-stacks --stack-name $PROJECT-$ENV-server --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
curl -fsS "$API_URL/health/ready"
```

The stack completes only after the instance reports `/health/ready`, which takes about 5 minutes: package install, a ~2 GB image pull and encoder load. CloudFront itself can take a few more minutes to propagate. With no default VPC, pass any VPC plus a **public** subnet in it.

### 4. Client (Amplify)

```bash
aws cloudformation deploy --stack-name $PROJECT-$ENV-client \
  --template-file infra/cloudformation/03-client.yaml \
  --parameter-overrides ProjectName=$PROJECT EnvName=$ENV BranchName=$BRANCH GitHubAccessToken="$GITHUB_TOKEN" ApiUrl=$API_URL

APP_ID=$(aws cloudformation describe-stacks --stack-name $PROJECT-$ENV-client --query "Stacks[0].Outputs[?OutputKey=='AppId'].OutputValue" --output text)
aws amplify start-job --app-id $APP_ID --branch-name $BRANCH --job-type RELEASE   # CloudFormation does not run the first build
```

### 5. Allow the console origin and restart the API

The client stack wrote `/svo/<env>/allowed-origins`. The API reads it only at start:

```bash
INSTANCE=$(aws cloudformation describe-stacks --stack-name $PROJECT-$ENV-server --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)
aws ssm send-command --instance-ids $INSTANCE --document-name AWS-RunShellScript --parameters commands="systemctl restart svo-api"
```

Open the `ConsoleUrl` output of the client stack, enter an analyst key in the connection settings, and submit a prediction.

## Day-to-day operations

| Task | How |
| --- | --- |
| Deploy a new client | Push to the branch; Amplify builds and publishes automatically. |
| Deploy a new API image | `aws codebuild start-build --project-name svo-api-image`, then run the restart command from step 5. |
| Pin or roll back the API | Redeploy the server stack with `ImageTag=<12-char sha>` (from ECR), then restart. This changes only the SSM parameter, not the instance. |
| Rotate or add API keys | `aws ssm put-parameter --name /svo/prod/credentials-json --type SecureString --overwrite --value '<json>'`, then restart. |
| API logs | CloudWatch log group `/svo/prod/api`; bootstrap log at `/var/log/svo-bootstrap.log` on the instance. |
| Shell on the instance | EC2 console → instance → **Connect → Session Manager**, or `aws ssm start-session --target <instance-id>`. Then `systemctl status svo-api` or `journalctl -u svo-api`. |
| Restore the database | Create a volume from a DLM snapshot in the same AZ, stop the service, swap the volume on `/dev/sdf`, and start the service. |

A restart takes the API offline for about 30–60 seconds (pull plus encoder load). There is no zero-downtime deploy with a single SQLite-backed instance.

## Cost (rough, before tax; check the AWS Pricing Calculator for your region)

| Item | Approx. per month |
| --- | --- |
| EC2 t3.medium, on-demand, always on | $30–35 |
| EBS gp3 30 GB root + 20 GB data, plus snapshots | $5 |
| Public IPv4 (Elastic IP) | $3.60 |
| ECR (10 images × ~2 GB, lifecycle-capped) | $2 |
| CloudFront, Amplify hosting, CodeBuild minutes at low traffic | under $5 |

That is roughly **$45 a month**. Stopping the instance when idle removes most of the EC2 cost. The Elastic IP keeps the CloudFront origin valid across stop and start.

## Known limitations before real production

- **CloudFront → EC2 is plain HTTP.** Browser to CloudFront traffic is encrypted, but the hop from CloudFront to the instance crosses the public internet unencrypted, API key included. That is acceptable for a development deployment. For production, add a domain and terminate TLS on the origin (an ALB with an ACM certificate, or a CloudFront VPC origin with the instance in a private subnet).
- **Send keys as `X-API-Key`**, which is what the console already does. CloudFront's managed origin request policies may not forward `Authorization: Bearer` to the origin.
- **Single AZ, single instance.** An AZ outage takes the API down until it is restored from a snapshot.
- **Hugging Face at build time.** A build fails if the hub is unreachable or the pinned revision disappears. Built images are unaffected.
- **The `latest` tag moves.** A reboot pulls the current `latest`. Pin `ImageTag` once you need repeatable deployments.
- **OS updates are not automated.** Add SSM Patch Manager, or replace the instance (redeploy with a new AMI) periodically.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| CodeBuild fails pulling `python:3.12-slim-bookworm` with `toomanyrequests` | Docker Hub anonymous rate limit on shared CodeBuild IPs. Store `{"username","token"}` in Secrets Manager and pass its ARN as `DockerHubSecretArn` to the ECR stack. |
| CodeBuild fails at `COPY` or `verify_runtime.py` | Files not committed or pushed (see Prerequisites), or a bundle file changed line endings (`training/.gitattributes` must be on the branch). |
| Server stack times out on `Ready` | No image in ECR yet, or `/svo/<env>/credentials-json` missing or invalid. Read `/var/log/svo-bootstrap.log` through Session Manager before the rollback deletes the instance, or redeploy with `--disable-rollback`. |
| Console shows "Cannot reach the API" | API not restarted after the client stack (step 5), or CloudFront still propagating. Check the browser console for CORS or CSP errors. |
| 401 from the API | Wrong key, or keys rotated without a restart. |

## Teardown

Delete the stacks in reverse order: `svo-prod-client`, `svo-prod-server`, `svo-ecr`. The data volume is snapshotted, and the ECR repository is retained along with its images. Delete those by hand if you no longer need them, together with the `/svo/prod/credentials-json` parameter.
