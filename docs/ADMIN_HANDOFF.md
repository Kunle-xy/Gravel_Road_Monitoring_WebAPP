# GravelRoad Iowa: administrator handoff and fresh-server setup

Last reviewed: November 12, 2026.

This guide is for an administrator who has the GitHub repository but has not
worked on the existing server. It covers a new installation and explains what
else must be transferred if existing users, uploads, and results must survive.

The commands target **Ubuntu Server 24.04 LTS, x86-64**, with PostgreSQL 16,
Redis, Python 3.12, GDAL 3.8.4, and systemd. Other distributions need equivalent
packages and paths. These are setup instructions checked against the repository;
they are not a claim that this entire procedure has been executed on a fresh VM.

## Contents

1. [What must be handed over](#1-what-must-be-handed-over)
2. [Architecture and prerequisites](#2-architecture-and-prerequisites)
3. [Prepare the Linux account and packages](#3-prepare-the-linux-account-and-packages)
4. [Clone the repository and install uv](#4-clone-the-repository-and-install-uv)
5. [Set up PostgreSQL](#5-set-up-postgresql)
6. [Set up Redis](#6-set-up-redis)
7. [Create AWS storage and access](#7-create-aws-storage-and-access)
8. [Set up CloudFront](#8-set-up-cloudfront)
9. [Create the backend environment file](#9-create-the-backend-environment-file)
10. [Install Python dependencies and report rendering](#10-install-python-dependencies-and-report-rendering)
11. [Install the dust model files](#11-install-the-dust-model-files)
12. [Initialize the database and approve users](#12-initialize-the-database-and-approve-users)
13. [Install the systemd services](#13-install-the-systemd-services)
14. [Publish the API through Cloudflare Tunnel](#14-publish-the-api-through-cloudflare-tunnel)
15. [Deploy the frontend](#15-deploy-the-frontend)
16. [Verify the installation](#16-verify-the-installation)
17. [Operate and update the application](#17-operate-and-update-the-application)
18. [Transfer existing production data](#18-transfer-existing-production-data)
19. [Backups and recovery](#19-backups-and-recovery)
20. [Troubleshooting](#20-troubleshooting)
21. [Final handoff checklist](#21-final-handoff-checklist)

## 1. What must be handed over

**A GitHub clone is the application source, not the complete deployed system.**

| Item | In GitHub? | What the incoming administrator needs |
|---|---|---|
| Backend/frontend source and lockfiles | Yes | Repository access and a known deployment commit |
| Real `.env` files | No | Securely supplied values, or newly created resources and secrets |
| PostgreSQL users/projects/job history | No | A database backup if preserving existing data |
| Raw TIFFs, videos, tiles, COGs, reports, profile pictures | No | Access to the existing S3 buckets, or a complete object transfer |
| AWS permissions | No | Own IAM identity and permission to manage the required resources |
| Cloudflare domain and tunnel | No | Domain/DNS access and a new tunnel, or an agreed tunnel migration |
| Vercel project settings | No | Project/team access, or a new Vercel project |
| Actual service definitions on the old server | Not fully | This guide provides portable replacements |
| Dust model weights and training label order | Not fully | Verified `yolo26l.pt` and `best_model_final.pt` from the maintainer |
| Approved email/domain entries | Only the management code | Recreate entries or restore the database |

The repository contains a legacy `FastAPI/yolov8s.pt`, but the current dust code
loads **`yolo26l.pt`**. The older file does not replace the currently required
detector or the trained dust classifier.

Choose the installation type before proceeding:

- **Fresh installation:** new empty database and storage, new user registration.
- **Production transfer:** preserve the database and S3 objects; follow
  [section 18](#18-transfer-existing-production-data) before opening to users.

Exchange secrets through the organization's approved secure channel. Do not put
actual keys, passwords, database dumps, or tunnel credentials in this document
or in Git. The sample values below are placeholders.

## 2. Architecture and prerequisites

### 2.1 How requests move through the system

```text
Browser
  ├─ frontend pages → Vercel Next.js application
  ├─ /api/* → Next.js rewrite → https://api.gravel.example.org
  │                              → Cloudflare Tunnel
  │                              → FastAPI at 127.0.0.1:8000
  ├─ uploads → presigned S3 URLs, directly from the browser
  └─ map tiles/profile pictures → CloudFront → private S3 origin

Local Linux server
  ├─ fastapi.service          API, authentication, upload/job requests
  ├─ celery-tiles.service     consumes queue "tiles"
  ├─ celery-analysis.service  consumes queue "celery"
  ├─ postgresql.service      persistent application data
  ├─ redis-server.service    task broker, task results, auth rate limiting
  └─ cloudflared.service     outbound API tunnel
```

The analysis worker handles rut, crown, corrugation, pothole, and dust jobs.
The tile worker downloads TIFFs, builds COGs, generates **PNG XYZ tiles** with
`gdal2tiles.py`, and uploads the results. Original DEMs supply analysis elevations;
display tiles are scaled images, not the analysis data source.

No separate TiTiler server, Celery Beat, Flower, Docker, Nginx, or public
PostgreSQL/Redis endpoint is required for the normal static-tile deployment.
`TITILER_URL` exists for a legacy fallback; that path is not the primary map flow.

### 2.2 Accounts and network

Prepare access to:

- A Linux server with sudo access, reliable storage, and outbound internet.
- The GitHub repository: `Kunle-xy/Gravel_Road_Monitoring_WebAPP`.
- An AWS account with S3, CloudFront, IAM, and optionally SES access.
- A domain managed in Cloudflare and permission to create a tunnel/DNS record.
- Vercel access, if using the existing hosting design.

Permit outbound HTTPS to AWS, package registries, Vercel, and browser map/report
providers. Cloudflare Tunnel needs outbound connectivity to its edge on port
7844; allow UDP for QUIC and/or TCP for HTTP/2. Do not open ports 5432, 6379,
8000, or 3000 to the internet just to make this architecture work.

Keep SSH access under your organization's firewall policy. Keep system time
synchronized: incorrect time can break JWT expiry and signed AWS requests.

### 2.3 Capacity and versions

An initial sizing suggestion is 8 CPU cores, 32 GB RAM, and at least 100 GB of
free SSD space, increased for large imagery and concurrent jobs. This is an
operational starting point, **not a measured minimum or capacity guarantee**.
Tile generation creates multiple temporary raster copies plus a tile directory;
reserve substantially more scratch space than the largest input file.

An NVIDIA GPU is optional for the application, but can substantially affect
dust inference throughput. CPU operation is supported by the current model
loading code. The dependency configuration downloads CUDA 12.4 PyTorch wheels,
which also increases environment size even on CPU-only machines.

| Component | Guide baseline |
|---|---|
| OS | Ubuntu Server 24.04 LTS, x86-64 |
| Python | 3.12, matching `FastAPI/.python-version` |
| Python GDAL binding | **3.8.4**, pinned in `FastAPI/pyproject.toml` |
| System GDAL | Match the binding; Noble packages provide 3.8.4 |
| PostgreSQL | 16 |
| Redis | Ubuntu 24.04 packaged Redis 7 |
| Node.js | Supported Node 22 or 24 installation; use the same major locally and in Vercel |
| Python/JS application packages | Versions in `FastAPI/uv.lock` and `webapp/package-lock.json` |

Ubuntu's [GDAL package listing](https://packages.ubuntu.com/noble/gdal-bin)
is why this guide targets Noble. GDAL's
[Python installation notes](https://gdal.org/en/stable/api/python/python_bindings.html)
explain the native-library dependency. Do not substitute a newer OS/GDAL version
without validating and updating the Python pin and lockfile together.

### 2.4 Names used throughout this guide

Replace these consistently with your own values:

| Example | Meaning |
|---|---|
| `graveladmin` | Linux account that owns and runs the application |
| `/home/graveladmin/GravelRoad_Iowa` | Checkout location |
| `gravel_app` | PostgreSQL login role |
| `gravel_road_app` | PostgreSQL database |
| `replace-with-your-raw-bucket` | Globally unique S3 bucket for uploads and some reports |
| `replace-with-your-assets-bucket` | Globally unique S3 bucket for tiles, COGs, pictures, some reports |
| `us-east-2` | Example AWS Region; use one consistent Region |
| `api.gravel.example.org` | Public API hostname |
| `roads.example.org` | Public frontend hostname |
| `REPLACE_DISTRIBUTION_ID` | CloudFront distribution ID |
| `REPLACE_TUNNEL_UUID` | Newly created Cloudflare tunnel UUID |

These example domains are not working service addresses. Reuse the old deployment's
resources only if their owners have explicitly transferred access.

## 3. Prepare the Linux account and packages

Run this section as an existing sudo-capable administrator. If the intended
application account already exists, skip its creation and use its actual path
in every later example.

```bash
sudo adduser graveladmin
sudo usermod -aG sudo graveladmin
sudo -iu graveladmin
```

Subsequent application commands assume you are logged in as `graveladmin`.
Use sudo only for operating-system configuration.

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo apt update
sudo apt install -y \
  git curl ca-certificates gnupg unzip build-essential pkg-config \
  python3.12 python3.12-dev python3.12-venv \
  postgresql-16 postgresql-client-16 redis-server \
  gdal-bin libgdal-dev libproj-dev proj-data proj-bin \
  libgeos-dev libpq-dev \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
  libffi-dev shared-mime-info fonts-dejavu-core \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2t64
```

The browser libraries support Chrome/Kaleido report images. Pango/font libraries
support the rendering packages declared by the backend. If a package was renamed
by a later OS release, resolve that package for your distribution rather than
omitting the native dependency silently.

```bash
python3.12 --version
gdalinfo --version
gdal-config --version
psql --version
redis-server --version
timedatectl status
df -h / /tmp
```

Confirm that `gdal-config --version` is **3.8.4** before installing the Python
environment. The service examples use real temporary storage in `/tmp`; watch
that filesystem as well as the project disk.

## 4. Clone the repository and install uv

```bash
cd /home/graveladmin
git clone https://github.com/Kunle-xy/Gravel_Road_Monitoring_WebAPP.git GravelRoad_Iowa
cd /home/graveladmin/GravelRoad_Iowa
git switch main
git rev-parse HEAD
```

For a private repository, configure the incoming administrator's own GitHub SSH
key or credential manager. Do not embed an access token in the clone URL or copy
the previous user's broken editor-specific credential helper.

Install uv as the application account, following the
[official uv installer](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/gravel-uv-install.sh
less /tmp/gravel-uv-install.sh
sh /tmp/gravel-uv-install.sh
export PATH="/home/graveladmin/.local/bin:$PATH"
uv --version
```

Quit `less` with `q`. The installer normally updates shell configuration;
the `export` makes uv available in this shell immediately.

Do not install the backend from the top-level `package.json`, and do not run
`FastAPI/main.py`; that file is a placeholder. The API entry point is
**`app.main:app` from the `FastAPI/` directory**.

## 5. Set up PostgreSQL

### 5.1 Start PostgreSQL and create a dedicated role/database

```bash
sudo systemctl enable --now postgresql
sudo -u postgres psql
```

At the PostgreSQL prompt:

```sql
CREATE ROLE gravel_app LOGIN;
\password gravel_app
CREATE DATABASE gravel_road_app OWNER gravel_app;
\q
```

Enter a strong new database password when `\password` prompts. A random hex
password avoids URL-reserved characters when composing `DATABASE_URL`.
Otherwise percent-encode the password in the URL; the actual PostgreSQL
password itself remains unencoded.

The application role owns this application's database and can create its schema.
Do not give it PostgreSQL superuser privileges.

### 5.2 Restrict the database to the local server

Locate the active configuration paths:

```bash
sudo -u postgres psql -Atc "SHOW config_file"
sudo -u postgres psql -Atc "SHOW hba_file"
```

On a standard Ubuntu installation, edit:

```bash
sudoedit /etc/postgresql/16/main/postgresql.conf
sudoedit /etc/postgresql/16/main/pg_hba.conf
```

In `postgresql.conf`, use:

```conf
listen_addresses = 'localhost'
password_encryption = 'scram-sha-256'
```

Ensure `pg_hba.conf` allows this role/database over loopback with SCRAM. Put
specific rules before conflicting broader rules; leave the local administrative
`postgres` peer-authentication rule intact:

```conf
host    gravel_road_app    gravel_app    127.0.0.1/32    scram-sha-256
host    gravel_road_app    gravel_app    ::1/128         scram-sha-256
```

```bash
sudo systemctl restart postgresql
psql -h 127.0.0.1 -U gravel_app -d gravel_road_app -W -c "SELECT current_user, current_database();"
```

Enter the password interactively. Expected user/database:
`gravel_app` / `gravel_road_app`.

Do not initialize tables yet if restoring a production dump; see section 18.

## 6. Set up Redis

Redis is required by **both** Celery and authentication rate limiting. A broken
Redis connection can affect login even if the database is healthy.

```bash
sudoedit /etc/redis/redis.conf
```

Set or update the existing directives, rather than appending duplicate active
settings. Replace the password placeholder with a new random hex password:

```conf
bind 127.0.0.1 ::1
protected-mode yes
requirepass REPLACE_REDIS_HEX_PASSWORD
appendonly yes
maxmemory-policy noeviction
```

The guide uses the packaged default Redis user with `requirepass`; if your
organization uses named ACL users, include the username in the Redis URLs too.
Keep the data directory on persistent storage. Configure a memory limit only
after sizing the workload; broker keys must not be evicted to make room.

```bash
sudo systemctl enable --now redis-server
sudo systemctl restart redis-server
redis-cli --askpass -h 127.0.0.1 ping
```

Enter the Redis password. Expected response: `PONG`.

Use Redis database **0** for the broker/rate limiter and database **1** for the
Celery result backend in this guide. `REDIS_PASSWORD` alone does not rewrite
connection URLs: both `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` must contain
the correct password. See [Redis security guidance](https://redis.io/docs/latest/operate/oss_and_stack/management/security/).

## 7. Create AWS storage and access

### 7.1 Create two S3 buckets

In the AWS console, choose the intended Region, then create:

1. **Raw bucket:** original DEM/orthophoto/hillshade TIFFs, video uploads, and
   rut/crown/corrugation reports and overlay GeoJSON.
2. **Assets bucket:** generated tiles, COGs, profile pictures, and pothole reports.

For each bucket:

- Use a globally unique name and record the exact Region.
- Keep **Block Public Access enabled**.
- Use Bucket owner enforced object ownership.
- Use default server-side encryption. SSE-S3 keeps the example IAM policy simple;
  SSE-KMS additionally needs the appropriate KMS grants for the app and CloudFront.
- Consider versioning according to the organization's retention/budget policy.
- Add a lifecycle rule to abort incomplete multipart uploads after a few days.
  This avoids abandoned upload parts accumulating indefinitely.

Do not use a static website endpoint for the CloudFront origin in section 8.

### 7.2 Configure CORS on both buckets

In each bucket's **Permissions → Cross-origin resource sharing**, paste this JSON
after replacing the frontend origin. Keep localhost entries only if local
development is needed:

```json
[
  {
    "AllowedOrigins": [
      "https://roads.example.org",
      "http://localhost:3000"
    ],
    "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "Content-Length", "Content-Range", "Accept-Ranges"],
    "MaxAgeSeconds": 3600
  }
]
```

If you use the Vercel-provided production hostname, include its **exact** origin
as well. Add explicitly approved preview origins if testing preview deployments.
An origin has no trailing slash or URL path.

`ETag` must be exposed: the browser reads each multipart part's ETag to complete
large uploads. Configure CORS on the assets bucket too because profile pictures
are uploaded there directly. CORS does not grant anonymous storage access; IAM,
bucket policies, and presigned URLs still control authorization. See
[S3 CORS elements](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ManageCorsUsing.html).

### 7.3 Create the application's IAM identity

Use a dedicated runtime IAM identity. On an ordinary local server the current
code is simplest to configure with a dedicated access-key pair in the backend
environment file. Do not use AWS account root credentials.

Attach a policy equivalent to the following, replacing both bucket names:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListApplicationBuckets",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation", "s3:ListBucketMultipartUploads"],
      "Resource": [
        "arn:aws:s3:::replace-with-your-raw-bucket",
        "arn:aws:s3:::replace-with-your-assets-bucket"
      ]
    },
    {
      "Sid": "ManageApplicationObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
        "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"
      ],
      "Resource": [
        "arn:aws:s3:::replace-with-your-raw-bucket/*",
        "arn:aws:s3:::replace-with-your-assets-bucket/*"
      ]
    }
  ]
}
```

This is bucket-scoped application access, not permission to administer all of
AWS. The administrator creating buckets/distributions/tunnels needs separate
provisioning permissions. The runtime app does not need broad CloudFront
administration rights to serve static tile URLs.

Keep the access key ID and secret access key for section 9. The same credentials
must be available to **FastAPI and both workers**. Most boto3 clients read the
process environment directly, while raster extraction also reads the Settings
values and exports credentials for GDAL. Therefore an AWS profile that works
only in your interactive terminal is insufficient for these service examples.

The current Settings schema does not declare `AWS_SESSION_TOKEN`, and raster
extraction explicitly exports access-key fields. If institutional policy
requires short-lived credentials or roles, validate/adapt that credential path
and its renewal before relying on it for unattended service operation.

### 7.4 Optional AWS CLI

Install AWS CLI v2 using the
[official platform instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
if you want command-line bucket management, transfers, or backups. Configure the
administrator's profile separately with `aws configure` or your institution's
SSO workflow. This does not replace the service environment file.

For the x86-64 Linux baseline, the official installer commands are:

```bash
curl -fSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/gravel-awscliv2.zip
unzip /tmp/gravel-awscliv2.zip -d /tmp/gravel-awscli-install
sudo /tmp/gravel-awscli-install/aws/install
aws --version
```

Use a new extraction directory if that temporary directory already exists.
The linked AWS instructions include signature verification and update procedures;
follow the organization's download-verification policy before running an installer.

Do not put AWS keys in frontend environment variables: anything prefixed
`NEXT_PUBLIC_` is intended to be available to browser-side code.

## 8. Set up CloudFront

Create a CloudFront distribution with:

1. Origin: the **assets bucket's S3 REST origin**, not its website endpoint.
2. Origin access: **Origin Access Control (OAC)**, signing requests.
3. Viewer protocol: redirect HTTP to HTTPS.
4. Viewer methods: GET and HEAD; enable OPTIONS if using an origin-based CORS policy.
5. No origin path prefix: the app already generates paths such as
   `tiles/USER_UUID/FILE_UUID/Z/X/Y.png`.
6. A cache policy appropriate for versioned/static tile paths.
7. A CORS response headers policy if browser canvas/image operations need
   cross-origin access. For this deployment, a policy returning the allowed
   frontend origin for GET/HEAD is suitable. Alternatively forward Origin and
   use S3 CORS with a cache policy that handles Origin correctly.

Apply the OAC bucket policy proposed by AWS to the assets bucket. Its read
permission should be restricted to this distribution. A typical statement is:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontRead",
      "Effect": "Allow",
      "Principal": {"Service": "cloudfront.amazonaws.com"},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::replace-with-your-assets-bucket/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::REPLACE_AWS_ACCOUNT_ID:distribution/REPLACE_DISTRIBUTION_ID"
        }
      }
    }
  ]
}
```

Record the distribution hostname, for example `dexample123.cloudfront.net`.
Set `AWS_CLOUDFRONT_DOMAIN` to **the hostname only**, without `https://` or `/`.
Wait for distribution deployment before testing tiles. OAC setup is described in
[AWS's S3 origin guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).

Private S3 origin access does **not** mean viewer access to CloudFront requires
login. The current tile/profile-picture URLs do not use CloudFront signed URLs
or cookies; anyone with their URL may be able to retrieve them. OAC also grants
read access to other permitted assets-bucket objects. If the institution requires
per-user protection for every derived object, that needs an application/CDN
authorization change, not merely another environment variable.

## 9. Create the backend environment file

Create the file in **`FastAPI/`**, where Pydantic and the services expect it:

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
umask 077
touch .env
chmod 600 .env
nano .env
```

Paste and replace all `REPLACE_...` and example resource values:

```dotenv
DATABASE_URL=postgresql://gravel_app:REPLACE_DB_HEX_PASSWORD@127.0.0.1:5432/gravel_road_app

SECRET_KEY=REPLACE_WITH_A_NEW_RANDOM_SIGNING_SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

AWS_ACCESS_KEY_ID=REPLACE_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=REPLACE_AWS_SECRET_ACCESS_KEY
AWS_REGION=us-east-2
S3_BUCKET_RAW=replace-with-your-raw-bucket
S3_BUCKET_NAME=replace-with-your-assets-bucket
AWS_CLOUDFRONT_DOMAIN=dexample123.cloudfront.net

FRONTEND_URL=https://roads.example.org

REDIS_PASSWORD=REPLACE_REDIS_HEX_PASSWORD
CELERY_BROKER_URL=redis://:REPLACE_REDIS_HEX_PASSWORD@127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://:REPLACE_REDIS_HEX_PASSWORD@127.0.0.1:6379/1

EMAIL_PROVIDER=console
SES_FROM_EMAIL=
RESEND_API_KEY=
RESEND_FROM_EMAIL="Gravel Road Iowa <onboarding@resend.dev>"
EMAIL_VERIFY_EXPIRE_HOURS=24
```

Generate a signing secret locally, then paste it into `.env`:

```bash
python3.12 -c 'import secrets; print(secrets.token_hex(32))'
```

Do not use `export` statements or shell command substitutions inside `.env`.
Keep it compatible with both Pydantic dotenv parsing and systemd EnvironmentFile.
Use straight quotes, not typographic quotes. Do not commit it.

The unlisted settings `AWS_CLOUDFRONT_ARN`,
`AWS_CLOUDFRONT_ORIGIN_ACCESS_ID`, and `TITILER_URL` have defaults and are not
needed for the standard path. `S3_BUCKET_NAME` and `S3_BUCKET_RAW` are different
settings even if older comments describe their names differently.

### Optional outbound email

Current approved-user registration sets the account active and email-verified
immediately; it does not require an SES verification email to let that user
register. Verification/resend endpoints and email providers still exist.

`EMAIL_PROVIDER=console` logs verification links rather than sending mail.
For actual outbound email choose one:

- **SES:** verify your sender/domain in the same Region as `AWS_REGION`, add its
  DNS records, set `EMAIL_PROVIDER=ses` and `SES_FROM_EMAIL`, and grant runtime
  `ses:SendEmail` on the intended SES identity ARN. Request production access if
  you need arbitrary recipients; SES sandbox recipient restrictions apply.
  See [SES production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).
- **Resend:** verify your sender domain, provide `RESEND_API_KEY` and
  `RESEND_FROM_EMAIL`, and set `EMAIL_PROVIDER=resend`. No SES permission is then
  necessary for this mail path.

Use the approved institution's sender identity; do not copy a previous owner's
personal sending credentials.

## 10. Install Python dependencies and report rendering

### 10.1 Synchronize the locked environment

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
uv venv --python /usr/bin/python3.12
uv sync --locked
```

`uv sync --locked` uses `pyproject.toml` and the committed lockfile and rejects a
stale lock rather than silently resolving new package versions. Allow time and
disk space for the PyTorch/CUDA downloads. Do not substitute the older
`requirements.txt` as the authoritative dependency set.

If GDAL's source build fails because it needs installed NumPy/build tools, with
the system GDAL version already confirmed as 3.8.4, use:

```bash
uv pip install 'numpy>=2.4.3' setuptools wheel
uv sync --locked --no-build-isolation-package gdal
```

This targeted fallback makes the installed build dependencies available to the
GDAL build; it is not a workaround for a mismatched native GDAL version. See
[uv's build-isolation option](https://docs.astral.sh/uv/reference/cli/#uv-sync--no-build-isolation-package).

Check native and Python tooling together:

```bash
.venv/bin/python -c 'from osgeo import gdal; import rasterio, numpy; print("GDAL", gdal.VersionInfo()); print("Rasterio", rasterio.__version__); print("NumPy", numpy.__version__)'
.venv/bin/gdal2tiles.py --help
.venv/bin/python -c 'import torch, torchvision, cv2; print("torch", torch.__version__); print("CUDA available", torch.cuda.is_available())'
```

The tile worker invokes `gdal2tiles.py` by name. The systemd PATH in section 13
includes `.venv/bin` to resolve the matching Python/GDAL command. Do not leave a
system GDAL Python script resolving against the wrong interpreter unnoticed.

### 10.2 Install Chrome for static report images

Kaleido 1 uses an external Chrome/Chromium installation for Plotly PNG export.
Run the installer as **the application account**, not root:

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
.venv/bin/plotly_get_chrome -y
.venv/bin/python -c 'import plotly.graph_objects as go; data=go.Figure(go.Scatter(y=[1,3,2])).to_image(format="png"); assert data.startswith(bytes([137,80,78,71])); print("Report PNG rendering OK")'
```

If Chrome is installed manually, ensure the application account can execute it;
Kaleido's `BROWSER_PATH` can point to a known executable in the service environment.
If a later clean environment installation removes the bundled browser directory,
rerun the browser install/render check before restarting analysis workers.
See [Plotly static image export](https://plotly.com/python/static-image-export/).

An API that starts successfully can still fail crown/report jobs if this browser
check is skipped. Interactive HTML alone is not a sufficient rendering test.

## 11. Install the dust model files

Obtain the correct model files and their SHA-256 checksums from the outgoing
maintainer. Stage the trusted files on the new server, then install them as the
application account:

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
install -m 600 /secure/staging/yolo26l.pt ./yolo26l.pt
install -m 600 /secure/staging/best_model_final.pt ./app/workers/dust/best_model_final.pt
sha256sum yolo26l.pt app/workers/dust/best_model_final.pt
```

`/secure/staging/` is an example transfer location, not part of the repository.
The detector path is relative to the process working directory; the classifier
path is relative to `app/workers/dust/detection.py`. The API needs detector access
for live video streaming, and the analysis worker needs both files for saved
dust analysis.

```bash
.venv/bin/python - <<'PY'
from app.workers.dust.detection import get_yolo_model, get_dust_classifier
get_yolo_model()
get_dust_classifier()
print("Dust models loaded")
PY
```

Do not depend on a first production request downloading weights automatically.
The trained dust classifier is a project artifact, not a generic downloadable
ResNet replacement. The code's `DUST_CLASSES` order is currently
`No Dust`, `Low Dust`, `High Dust`, while a function comment states a different
index order. Obtain the training class mapping and check predictions against
known labeled clips before accepting this feature's results.

If no models are available, document dust as unavailable; the rest of the stack
can still be commissioned. Do not describe that installation as fully supporting
dust analysis.

## 12. Initialize the database and approve users

### 12.1 Fresh database only

From `FastAPI/`, create the tables declared by the current models:

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
.venv/bin/python - <<'PY'
from app.database import Base, engine
import app.models
Base.metadata.create_all(bind=engine)
print("Application tables created")
PY
```

The API also calls `create_all()` at startup. Explicit initialization makes
failures visible before systemd is involved. It does **not** create a database
login or the database itself; those were created in section 5.

Do not run every file under `FastAPI/migrations/` blindly. These are historical
SQL patches, including duplicate COG migrations and a folder trigger that is
not safely repeatable as written. `create_all()` creates missing tables but
**does not add missing columns or change existing constraints**. Restored older
databases need a reviewed schema upgrade; see section 18.

### 12.2 Approve the first user before registration

```bash
.venv/bin/python manage_approved.py add admin@example.org --note "Incoming administrator"
.venv/bin/python manage_approved.py list
```

Replace that address with the real user's email. The person then registers using
the website. There is no automatically created administrator account or default
password. The allowlist CLI grants application access, not a separate web-admin
role.

Other allowlist commands:

```bash
.venv/bin/python manage_approved.py add analyst@example.org
.venv/bin/python manage_approved.py remove analyst@example.org
.venv/bin/python manage_approved.py add-domain example.org
.venv/bin/python manage_approved.py remove-domain example.org
```

Approving a domain permits every address on that domain. Removing an individual
entry does not block that person if their domain is still approved. Removal gates
new registration/login; it is not a substitute for explicitly deactivating a
user/revoking existing sessions when immediate access removal is required.

### 12.3 Confirm settings and services can talk to their dependencies

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import text
from app.database import engine
from app.config import settings
import redis
import boto3

with engine.connect() as conn:
    assert conn.execute(text("SELECT 1")).scalar() == 1
print("PostgreSQL OK")
assert redis.Redis.from_url(settings.CELERY_BROKER_URL).ping()
assert redis.Redis.from_url(settings.CELERY_RESULT_BACKEND).ping()
print("Redis broker/results OK")

# Load the same environment values systemd will export to boto3 clients.
import os
os.environ["AWS_ACCESS_KEY_ID"] = settings.AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = settings.AWS_SECRET_ACCESS_KEY
s3 = boto3.client("s3", region_name=settings.AWS_REGION)
for bucket in (settings.S3_BUCKET_RAW, settings.S3_BUCKET_NAME):
    s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
    print("S3 list OK:", bucket)
PY
```

This read check does not prove PUT/GET/DELETE or browser CORS permissions; those
are checked with a real upload later. It prints no credentials.

## 13. Install the systemd services

These units replace machine-specific examples such as the repository's
`FastAPI/fastapi.service`, which hardcodes the old account/path and eight API
workers. Start conservatively on a new machine and increase concurrency only
after measuring RAM, CPU, scratch storage, GPU, and database usage.

Create each file with `sudoedit`. Do not paste unit contents directly into a shell.
All three units use the environment file from section 9 and the virtualenv
executables installed in section 10. Runtime services do not run `uv sync` or
download dependencies.

### 13.1 API: `/etc/systemd/system/fastapi.service`

```ini
[Unit]
Description=GravelRoad FastAPI
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=graveladmin
Group=graveladmin
WorkingDirectory=/home/graveladmin/GravelRoad_Iowa/FastAPI
EnvironmentFile=/home/graveladmin/GravelRoad_Iowa/FastAPI/.env
Environment="PATH=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin/gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 2 --timeout 300 --max-requests 100 --max-requests-jitter 20
Restart=always
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
```

### 13.2 Tiles: `/etc/systemd/system/celery-tiles.service`

```ini
[Unit]
Description=GravelRoad tile worker
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=graveladmin
Group=graveladmin
WorkingDirectory=/home/graveladmin/GravelRoad_Iowa/FastAPI
EnvironmentFile=/home/graveladmin/GravelRoad_Iowa/FastAPI/.env
Environment="PATH=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin/celery -A app.celery_app worker --loglevel=INFO --queues=tiles --concurrency=1 --hostname=tiles@%%h
Restart=always
RestartSec=5
TimeoutStopSec=infinity
UMask=0077

[Install]
WantedBy=multi-user.target
```

### 13.3 Analyses: `/etc/systemd/system/celery-analysis.service`

```ini
[Unit]
Description=GravelRoad analysis worker
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=graveladmin
Group=graveladmin
WorkingDirectory=/home/graveladmin/GravelRoad_Iowa/FastAPI
EnvironmentFile=/home/graveladmin/GravelRoad_Iowa/FastAPI/.env
Environment="PATH=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/graveladmin/GravelRoad_Iowa/FastAPI/.venv/bin/celery -A app.celery_app worker --loglevel=INFO --queues=celery --concurrency=1 --hostname=analysis@%%h
Restart=always
RestartSec=5
TimeoutStopSec=infinity
UMask=0077

[Install]
WantedBy=multi-user.target
```

The doubled `%%h` is intentional: systemd passes a literal `%h` to Celery, which
expands its hostname. The analysis queue is named **`celery`**, not `analysis`.
Do not start an extra terminal/background worker on the same machine unless
you intend it to consume production work too.

`TimeoutStopSec=infinity` allows Celery's warm shutdown to finish active jobs.
A stop/restart can therefore wait a long time; drain and schedule long jobs
before maintenance. Forcefully killing workers is not a routine deployment step.

For CUDA dust inference, validate PyTorch's multiprocessing behavior. If you hit
CUDA reinitialization errors with prefork, run the analysis worker with
`--pool=solo --concurrency=1` and recheck throughput; do not simply increase the
number of GPU worker children.

### 13.4 Load, validate, and start

```bash
sudo systemd-analyze verify /etc/systemd/system/fastapi.service /etc/systemd/system/celery-tiles.service /etc/systemd/system/celery-analysis.service
sudo systemctl daemon-reload
sudo systemctl enable --now fastapi celery-tiles celery-analysis
systemctl is-active fastapi celery-tiles celery-analysis
systemctl is-enabled fastapi celery-tiles celery-analysis
curl --fail http://127.0.0.1:8000/health
```

Each `is-active` line should be `active`; each `is-enabled` line should be
`enabled`. The health response reports `status: healthy`, but it is only a
process-level response, not a comprehensive dependency or job-processing test.

When taking over an existing server, also check for a historical
`celery-worker.service` that consumes both queues. It must not compete with the
two dedicated services using code loaded before deployment. Drain its work and
stop/disable that legacy service before accepting new jobs. See
[the mixed-version worker troubleshooting steps](operations.md#some-analyses-use-an-old-algorithm-despite-deploying-new-code).

```bash
sudo journalctl -u fastapi -n 80 --no-pager
sudo journalctl -u celery-tiles -n 80 --no-pager
sudo journalctl -u celery-analysis -n 80 --no-pager
```

The services run independently of interactive sessions and continue after users
log out. Enabled units start on reboot. Avoid globally disabling login cleanup
or enabling user-session linger just to keep these system services alive.

## 14. Publish the API through Cloudflare Tunnel

This section creates a **locally managed named tunnel**, matching the existing
architecture. A dashboard-managed token tunnel is an alternative; use one
management model consistently rather than mixing token and JSON credentials.

### 14.1 Install cloudflared

Follow the [Cloudflare Ubuntu package instructions](https://pkg.cloudflare.com/index.html).
For Ubuntu 24.04:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /tmp/gravel-cloudflare-main.gpg
sudo install -m 644 /tmp/gravel-cloudflare-main.gpg /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared noble main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
cloudflared --version
```

### 14.2 Authorize and create the tunnel

As `graveladmin`:

```bash
cloudflared tunnel login
cloudflared tunnel create gravel-road
```

Open the login URL in a browser that has access to the appropriate Cloudflare
account and authorize the domain. Record the generated tunnel UUID. Creation
writes a credentials JSON file under `/home/graveladmin/.cloudflared/`.

Create the system configuration directory and copy **your new tunnel's** JSON:

```bash
sudo install -d -m 700 /etc/cloudflared
sudo install -m 600 /home/graveladmin/.cloudflared/REPLACE_TUNNEL_UUID.json /etc/cloudflared/REPLACE_TUNNEL_UUID.json
sudoedit /etc/cloudflared/config.yml
```

Configuration contents:

```yaml
tunnel: REPLACE_TUNNEL_UUID
credentials-file: /etc/cloudflared/REPLACE_TUNNEL_UUID.json
ingress:
  - hostname: api.gravel.example.org
    service: http://127.0.0.1:8000
  - service: http_status:404
```

The hostname must be in the authorized Cloudflare DNS zone. Keep the final
catch-all ingress rule.

```bash
cloudflared tunnel route dns gravel-road api.gravel.example.org
sudo cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate
sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
systemctl is-active cloudflared
curl --fail https://api.gravel.example.org/health
```

These steps follow Cloudflare's
[named-tunnel creation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/)
and [Linux service setup](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/linux/).

If an old DNS record already uses that hostname, plan the cutover instead of
overwriting it during initial testing. Use a temporary hostname first.

If UDP/QUIC is blocked but TCP/7844 is permitted, add `protocol: http2` to the
tunnel config and restart cloudflared. If neither transport can reach the
edge, request the appropriate outbound network access.

Do not place an interactive Cloudflare Access login/challenge in front of this
API hostname without adapting the Next.js proxy to authenticate to it. Likewise,
cache rules must not cache `/auth/*` responses or authenticated API responses.
Cloudflare Tunnel provides the transport; application cookies provide user auth.

## 15. Deploy the frontend

Choose **A** for the existing architecture, or **B** to host Next.js locally.
Do not export this application as a static site: it uses server-side rewrites
and a Next.js API route for discovering URCI reference images.

### 15A. Vercel frontend

1. Sign into the incoming administrator's authorized Vercel team/account.
2. Import the GitHub repository, or transfer the existing Vercel project.
3. Set **Root Directory = `webapp`**. The repository root is not the Next.js app.
4. Use the Next.js framework preset, `npm ci` install command, and
   `npm run build` build command.
5. Select a supported Node.js major consistent with your local build, such as
   Node 22 or 24.
6. Set production environment variable:

   ```dotenv
   NEXT_PUBLIC_API_URL=https://api.gravel.example.org
   ```

7. Set production branch to `main`, deploy, and wait for **Ready**.
8. Add the production frontend domain, if using one, and finish its DNS setup.

Set the API URL before building. Changing it requires a new deployment because
Next.js builds the rewrite configuration. A browser request to `/api/auth/me`
should go through the frontend's own origin to the backend. Do not change
`webapp/app/lib/api.ts` to call a separate API origin for normal cookie requests;
the same-origin proxy is important to the current HttpOnly/SameSite cookie design.

Set `FRONTEND_URL` in the backend to the final **HTTPS frontend origin** and
restart FastAPI and both workers after changing `.env`. Confirm both S3 CORS
configurations include this origin. Backend production-cookie settings depend
on the scheme of `FRONTEND_URL`; leaving it as HTTP for a public deployment is
not correct.

Vercel's [monorepo configuration](https://vercel.com/docs/monorepos) and
[environment variable documentation](https://vercel.com/docs/environment-variables)
describe the project settings. A merge to `main` triggers a frontend deployment
only if that Git integration/production branch is configured.

For local frontend development, install a supported Node.js using the
[official Node.js download instructions](https://nodejs.org/en/download), then:

```bash
cd /home/graveladmin/GravelRoad_Iowa/webapp
node --version
npm ci
nano .env.local
```

For local development only, `.env.local` can contain:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

```bash
npm run dev
```

Use `http://localhost:3000` in your browser, since the API's development CORS
allowlist includes that origin. See the
[Next.js installation requirements](https://nextjs.org/docs/app/getting-started/installation).

### 15B. Optional: run Next.js on the local server too

Install Node.js system-wide from an approved source so `/usr/bin/node` and
`/usr/bin/npm` are available to systemd. If installed under a version manager,
substitute its absolute paths and PATH in the unit; systemd does not load your
interactive shell profile.

One Ubuntu option is the NodeSource Node 22 package repository. If approved by
your organization, inspect and run its setup script, then install the package:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/gravel-node-setup.sh
less /tmp/gravel-node-setup.sh
sudo bash /tmp/gravel-node-setup.sh
sudo apt install -y nodejs
node --version
npm --version
command -v node
command -v npm
```

This is a third-party OS package repository; the
[NodeSource distribution documentation](https://nodesource.com/products/distributions)
and the official Node.js download page describe the available installation paths.
Do not assume Ubuntu's unmodified `apt install nodejs` package is new enough
for the repository's Next.js version. Verify the version before building.

```bash
cd /home/graveladmin/GravelRoad_Iowa/webapp
node --version
npm ci
nano .env.local
```

For this same-machine production frontend, use:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

```bash
npm run build
```

Create `/etc/systemd/system/gravel-webapp.service`:

```ini
[Unit]
Description=GravelRoad Next.js frontend
Wants=network-online.target
After=network-online.target fastapi.service

[Service]
Type=simple
User=graveladmin
Group=graveladmin
WorkingDirectory=/home/graveladmin/GravelRoad_Iowa/webapp
Environment=NODE_ENV=production
Environment=NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/npm run start -- --hostname 127.0.0.1 --port 3000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gravel-webapp
```

Add a second hostname ingress **before** the catch-all in the existing
`/etc/cloudflared/config.yml`:

```yaml
  - hostname: roads.example.org
    service: http://127.0.0.1:3000
```

Then:

```bash
cloudflared tunnel route dns gravel-road roads.example.org
sudo cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate
sudo systemctl restart cloudflared
```

Set backend `FRONTEND_URL=https://roads.example.org` and update S3 CORS just as
for Vercel. The browser still calls `/api/*` on the frontend; Next.js forwards
those requests locally. No public port 3000 is required.

Keep the API's public URL for direct API checks and any features that need it.
The current library also derives a WebSocket URL from `NEXT_PUBLIC_API_URL`;
if a future browser feature uses that URL, a localhost backend URL cannot be
used by remote browsers and needs a public routing design.

## 16. Verify the installation

### 16.1 Processes, boot configuration, and listening addresses

```bash
systemctl is-active postgresql redis-server fastapi celery-analysis celery-tiles cloudflared
systemctl is-enabled postgresql redis-server fastapi celery-analysis celery-tiles cloudflared
sudo ss -ltnp
curl --fail http://127.0.0.1:8000/health
curl --fail https://api.gravel.example.org/health
curl --fail https://roads.example.org/api/health
```

On Ubuntu, `postgresql.service` may show `active (exited)` because it manages
cluster units. Verify the actual cluster with `pg_lsclusters` and a SQL query.
Check that PostgreSQL, Redis, FastAPI, and optional local Next.js are bound to
loopback, not public interfaces.

### 16.2 Worker queues and regression tests

```bash
cd /home/graveladmin/GravelRoad_Iowa/FastAPI
.venv/bin/python - <<'PY'
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from app.celery_app import celery_app
inspector = celery_app.control.inspect(timeout=10)
print("Worker replies:", inspector.ping())
print("Worker queues:", inspector.active_queues())
PY
.venv/bin/python -m unittest discover -s tests -v
```

This check loads the reviewed `.env` into the process environment before importing
Celery, matching how systemd supplies credentials. Calling a CLI directly from a
shell with no exported AWS keys can otherwise initialize boto3 with a different
credential provider. Do not `source` an unreviewed environment file as shell code.

Expect a worker consuming `tiles` and one consuming `celery`. The sampling tests
exercise horizontal/vertical road direction and rotated polygons; they do not
replace an end-to-end AWS/browser test.

### 16.3 Browser acceptance test

1. Open the deployed frontend and register an approved email.
2. Log in, refresh the page, and confirm the session still works.
3. Create a project. The current limit is **10 projects per user**.
4. Upload a small, valid, georeferenced DEM. Use projected horizontal coordinates
   in meters and elevations in meters; the analysis calculations assume these
   units. Upload orthophoto/hillshade imagery separately if needed.
5. Confirm tiling progresses to completed and the layer appears on the map.
6. Inspect an actual tile request in browser developer tools. Request that exact
   CloudFront URL; a guessed `15/0/0.png` is not a valid general health test.
7. Draw a polygon within DEM coverage. Run rut, crown, and corrugation jobs.
8. Test both road directions and a rotated polygon. Confirm reports load and
   map overlays align. Horizontal is the default direction; rut/crown sample
   across the road and corrugation along it, following polygon rotation.
9. Test a pothole polygon and its 3D report.
10. Test an upload larger than 100 MB to exercise multipart/ETag CORS behavior.
11. Test a profile picture, which uses the assets bucket upload CORS settings.
12. If models were supplied, test video preview and saved dust analysis with a
    known labeled clip. Live preview and saved classification are different paths.
13. Save a Final URCI record and verify its history after refreshing.
14. Log out of SSH, log back in, and confirm the system services still run.
15. Schedule a reboot test and recheck all services afterward.

There is currently a per-project limit of one DEM plus one combined
orthophoto/hillshade slot. Loose Aggregate and Drainage are placeholder panels.
Final URCI is a manual chart-assisted calculation, not an automatic end-to-end
road rating generated from all analysis jobs.

Dust live streaming uses a long-lived MJPEG response. If a Vercel/proxy request
duration limit interrupts it, verify the stream against the origin and choose a
hosting/proxy configuration that supports the required duration. Do not assume
Celery settings control a streaming request handled by FastAPI.

## 17. Operate and update the application

### 17.1 Routine service commands

```bash
sudo systemctl status fastapi celery-analysis celery-tiles cloudflared --no-pager
sudo journalctl -u fastapi -f
sudo journalctl -u celery-analysis -f
sudo journalctl -u celery-tiles -f
sudo journalctl -u cloudflared -f
```

Each `journalctl -f` command runs until Ctrl+C; stopping log viewing does not
stop the service. Do not launch the repository's legacy background-worker
scripts on top of the installed units. Some scripts hardcode the original
username, paths, or database access values and should be reviewed before reuse.

Useful resource checks:

```bash
df -h / /tmp
free -h
sudo -u postgres psql -d gravel_road_app -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname = 'gravel_road_app' GROUP BY state;"
```

The SQLAlchemy pool configuration is **per process**, not one 30-connection
budget for the entire installation. API workers and Celery children each have
their own process resources. Increase concurrency only after checking database
connection usage. Each tile task can launch four GDAL subprocesses internally.

### 17.2 Deploy updates

Arrange a maintenance window and drain active long-running jobs before changing
dependencies. Back up the database before schema changes.

```bash
cd /home/graveladmin/GravelRoad_Iowa
git status --short
git rev-parse HEAD
```

Record the commit as the rollback reference. If the working tree is not clean,
review it before proceeding; do not reset or overwrite somebody else's work.

```bash
sudo systemctl stop fastapi celery-analysis celery-tiles
git switch main
git pull --ff-only origin main
cd FastAPI
uv sync --locked
.venv/bin/python -m unittest discover -s tests -v
```

Apply any reviewed schema migration and repeat the rendering/model checks if
their dependencies changed. Then:

```bash
sudo systemctl start fastapi celery-analysis celery-tiles
systemctl is-active fastapi celery-analysis celery-tiles
curl --fail http://127.0.0.1:8000/health
```

If systemd unit files changed, run `sudo systemctl daemon-reload` before starting
the services. If only `.env` changed, restart the affected services; daemon-reload
does not reload a running process's environment.

For Vercel, wait for the production deployment from `main` to be Ready. For
local Next.js:

```bash
cd /home/graveladmin/GravelRoad_Iowa/webapp
npm ci
npm run build
sudo systemctl restart gravel-webapp
```

Repeat the public health checks and a small analysis. Old analysis results do
not automatically recalculate after code changes.

### 17.3 Rollback

Keep the previous commit identifier and a matching database backup. To roll back,
stop writes/workers, check out the reviewed previous deployment revision, restore
its dependency environment, and redeploy the matching frontend. Restore the
database only if the migration requires it and the restore has been planned;
doing so discards later writes. A Git checkout alone cannot reverse all schema
or data changes.

## 18. Transfer existing production data

Use this section when the new administrator must retain the current accounts,
project history, uploaded files, and reports. A fresh clone plus empty database
does not preserve any of those records.

### 18.1 Inventory and prepare a cutover

Record, through a secure handoff:

- Deployed commit and lockfiles on the old server.
- Database name, role ownership, extensions, and PostgreSQL version.
- Both S3 bucket names/Regions and CloudFront distribution.
- The actual public frontend/API domains and their owners.
- Required model files, checksums, and training class mapping.
- Service settings, worker concurrency, environment values, and backup schedule.

Build the new server with a separate test API hostname. Verify it before moving
production traffic. Avoid letting old and new workers consume the same broker
unless that is a deliberate, compatible rollout.

Stop accepting writes on the old application during the final snapshot. Drain
workers before taking the final database/object snapshot so records and objects
represent the same point in time. Do not run the old and new writable production
stacks against unrelated copies of the same database.

### 18.2 Back up the old database

On the old server, using the **actual old database name**, run an interactive
password-authenticated dump or the institution's approved local backup method:

```bash
umask 077
pg_dump -h 127.0.0.1 -U OLD_DATABASE_ROLE -d OLD_DATABASE_NAME -W \
  --format=custom --no-owner --no-acl --file=gravel-transfer.dump
```

Transfer the dump securely and verify a checksum at both ends. Do not upload it
to GitHub. Use a compatible `pg_dump`/`pg_restore` version; the client must not
be older than the server it is dumping.

### 18.3 Restore before table initialization

Create the new role and **empty** database as in section 5, but do not run the
section 12 `create_all()` command or start FastAPI before restoring.

On the new server, as the new database owner:

```bash
pg_restore -h 127.0.0.1 -U gravel_app -d gravel_road_app -W \
  --no-owner --no-acl --exit-on-error /secure/staging/gravel-transfer.dump
```

Use a newly created empty target database for this command; do not run it over
a populated database and ignore errors. This guide deliberately does not give
an automatic drop-database command.

### 18.4 Compare restored schema with current models

Before exposing the API, run this read-only column comparison from `FastAPI/`:

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import inspect
from app.database import Base, engine
import app.models
inspector = inspect(engine)
for table in Base.metadata.sorted_tables:
    if not inspector.has_table(table.name):
        print("MISSING TABLE:", table.name)
        continue
    present = {column["name"] for column in inspector.get_columns(table.name)}
    missing = set(table.columns.keys()) - present
    if missing:
        print("MISSING COLUMNS:", table.name, sorted(missing))
print("Column comparison complete; review constraints, defaults, and indexes separately.")
PY
```

Review findings and apply the appropriate historical SQL patches or a new
reviewed migration. For an individual reviewed patch, the command form is:

```bash
psql -h 127.0.0.1 -U gravel_app -d gravel_road_app -W \
  -v ON_ERROR_STOP=1 -f migrations/005_add_overlay_error_fields.sql
```

That example only adds overlay error columns; it does not upgrade every possible
older schema. Some models/fields have no comprehensive migration chain in this
repository. Missing overlay URL/key fields, newer job tables, folder cascade
constraints, and authentication fields must all be accounted for. Alembic is a
dependency, but the repository does not contain a complete configured Alembic
upgrade history to replace this review.

### 18.5 Preserve or transfer S3 objects

**Simplest handoff:** retain the existing buckets and CloudFront distribution,
grant the new runtime IAM identity access, and use their names in the new
environment. Existing database rows keep their original bucket/key references.

If moving to new buckets/accounts, copy both buckets completely with an approved
AWS profile and preserve object keys. For example:

```bash
aws s3 sync s3://OLD_RAW_BUCKET s3://NEW_RAW_BUCKET --source-region us-east-2 --region us-east-2
aws s3 sync s3://OLD_ASSETS_BUCKET s3://NEW_ASSETS_BUCKET --source-region us-east-2 --region us-east-2
```

Use the actual source and destination Regions. No `--delete` flag is needed.
Cross-account copies may need additional source, destination, and KMS permissions.
`s3 sync` does not copy bucket policies, CORS, lifecycle rules, or the complete
version history. Recreate those settings separately and validate inventory/size
and checksums appropriate to the transfer.

Changing `.env` alone is not enough for existing rows. Review/update stored
`tiff_files.s3_bucket`, `video_files.s3_bucket`, `tile_url_template`, profile
picture URLs, report URLs, and other saved storage references. Report/overlay
keys often remain usable if their paths are preserved, but their signed URLs
may need regeneration. Plan and test this data migration rather than performing
an unreviewed global string replacement.

Several job endpoints return stored presigned report/overlay URLs. Those URLs
expire, and deleting the signing identity can invalidate them sooner. The code
does not consistently regenerate every saved URL on every read. Check older
results explicitly; re-signing from the saved S3 keys or regenerating a report
may be necessary.

### 18.6 Sessions, allowlist, jobs, and DNS

- Preserve account password hashes through the database restore; users should
  not need to re-register to retain their project ownership.
- Decide whether to preserve `SECRET_KEY` or intentionally end existing access
  sessions. If changing it, also plan refresh-token revocation if the goal is
  to force everyone to log in again; changing the signing key alone does not
  revoke database-backed refresh tokens.
- Check `manage_approved.py list`. For a legacy database missing allowlist entries,
  `manage_approved.py seed` deliberately approves all existing registered users;
  use it only if that matches the intended access policy.
- Do not copy an old Redis queue blindly. Drain old work first, then inspect any
  `pending`/`processing` database jobs and retry/reconcile them deliberately.
  The database retains job history; an empty new broker does not resume all
  interrupted jobs by itself.
- Change the Cloudflare DNS/tunnel route only after the new origin works. Do not
  keep two connectors for the same tunnel pointing at incompatible independent
  deployments: traffic can reach either connector.
- Update/redeploy Vercel if the API hostname changes, update origins in `.env`
  and S3 CORS, then perform the browser acceptance test before retiring the old
  server and credentials.

## 19. Backups and recovery

### 19.1 What to back up

| Component | Backup approach |
|---|---|
| PostgreSQL | Scheduled custom-format dumps or the institution's database backup system |
| S3 | Versioning/retention and, if required, separate-account or offsite copies |
| `.env` | Encrypted secret store, with ownership/access records |
| Cloudflare credentials/config | Secure backup or documented ability to recreate the tunnel |
| Service units | Configuration repository without secrets, or secure system backup |
| Dust model files | Trusted artifact storage plus checksums and label mapping |
| Deployed revision | Git commit plus lockfiles |

Redis append-only persistence helps broker recovery, but is not a replacement
for the persistent database/object backups. Decide whether broker restoration
should replay work; replaying already completed jobs needs care.

### 19.2 Example scheduled database backup

As the application account, create a restricted backup directory and PostgreSQL
password file:

```bash
install -d -m 700 /home/graveladmin/backups/gravel
umask 077
nano /home/graveladmin/.pgpass
chmod 600 /home/graveladmin/.pgpass
```

Contents (actual password goes only in this local file):

```text
127.0.0.1:5432:gravel_road_app:gravel_app:REPLACE_ACTUAL_DB_PASSWORD
```

Create `/home/graveladmin/backups/gravel/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
umask 077
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
/usr/bin/pg_dump -h 127.0.0.1 -U gravel_app -d gravel_road_app \
  --format=custom --no-owner --no-acl \
  --file="/home/graveladmin/backups/gravel/gravel-${backup_stamp}.dump"
```

```bash
chmod 700 /home/graveladmin/backups/gravel/backup.sh
/home/graveladmin/backups/gravel/backup.sh
sudo apt install -y cron
sudo systemctl enable --now cron
crontab -e
```

Example daily cron entry:

```cron
15 2 * * * /home/graveladmin/backups/gravel/backup.sh >> /home/graveladmin/backups/gravel/backup.log 2>&1
```

Add monitored failure notification, retention cleanup, and off-server encrypted
copies according to policy. A successful local dump on the same disk is not
adequate disaster recovery. Test restoration to an isolated database periodically.
See [PostgreSQL backup/restore guidance](https://www.postgresql.org/docs/16/backup-dump.html).

## 20. Troubleshooting

| Symptom | Check and remedy |
|---|---|
| Missing Settings fields | Confirm `.env` is in `FastAPI/`, WorkingDirectory is correct, and service EnvironmentFile points to it. |
| AWS works in shell but fails in service | The runtime user/environment differs. Verify EnvironmentFile and both GDAL and boto3 credentials; a terminal AWS profile alone is insufficient. |
| GDAL version/build error | Compare `gdal-config --version` with pinned `gdal==3.8.4`; install matching native headers/libraries before rebuilding. |
| NumPy `_ARRAY_API` or GDAL import errors | Rebuild the GDAL binding against the installed NumPy using the targeted no-build-isolation fallback; repeat import and tiling checks. |
| `gdal2tiles.py` not found | Check `.venv/bin` and service PATH; test the script with the application interpreter. |
| Login/register gives 403 | Add the email/domain using `manage_approved.py`; restarting the server does not bypass the allowlist. |
| Login gives 423 | The account is temporarily locked after failed attempts; inspect auth behavior and allow the lockout to expire. |
| Login seems successful but next request is 401 | Check same-origin `/api` rewriting, cookie Secure/SameSite settings, HTTPS `FRONTEND_URL`, and browser cookies. |
| Authentication raises Redis errors | Check Redis is active, passwords match, and both URLs contain credentials. |
| Small upload works, large upload fails | Check multipart endpoints, raw bucket CORS, exposed `ETag`, and IAM multipart permissions. |
| Profile picture upload fails | Configure assets bucket PUT CORS too; raw bucket CORS alone is insufficient. |
| Upload completed but tiles never process | Ensure a worker consumes `tiles`; inspect celery-tiles logs and free `/tmp` space. |
| Analysis never processes | Ensure a worker consumes `celery`, not a queue named `analysis`; inspect job rows and worker logs. |
| Report generation fails after detection | Repeat Chrome/Kaleido PNG check as the application user; inspect missing shared-library/font errors. |
| Tile URLs return 403 | Check OAC origin/policy, correct assets bucket, exact object key, and deployed CloudFront distribution. |
| Old reports/overlays return 403 | Their saved presigned URLs may have expired or the signing credentials changed. Check the object key and regenerate the URL/report. |
| Cloudflare 502 | Check FastAPI is running at the ingress target; test `127.0.0.1:8000/health` first. |
| Cloudflare tunnel disconnected | Inspect cloudflared logs, tunnel credentials, DNS, and outbound 7844; try HTTP/2 if QUIC is blocked. |
| `sudo` asks for a password or needs a terminal | Run the administrative command from an interactive SSH terminal with the incoming admin's sudo privileges. |
| Models missing or wrong architecture | Obtain the correct trained artifacts; `yolov8s.pt` is not the model named by current code. |
| Dust severity labels look reversed | Verify training class order against `DUST_CLASSES` and known labeled test clips. |
| GPU memory/fork failures | Use one analysis process initially; validate CUDA/driver compatibility and consider `--pool=solo`. |
| Vercel build runs wrong package | Set Root Directory to `webapp`; use its package-lock and build command. |
| API hostname changed but frontend still calls old one | Set `NEXT_PUBLIC_API_URL` and redeploy/rebuild the frontend. |
| Server reboot leaves jobs unavailable | Check `is-enabled` for both workers, PostgreSQL, Redis, FastAPI, and cloudflared. |
| Restored database raises undefined-column errors | `create_all()` does not upgrade existing columns; compare models and apply reviewed migrations. |

Additional repository-specific caveats:

- COGs generated by the tile worker are stored in the assets bucket, but the
  legacy `/files/{id}/cog-file` path uses the file's original bucket with the COG
  key. If that fallback fails, investigate the bucket/key pair rather than
  making either bucket public. Static tile viewing and original-DEM analyses
  use their own paths.
- Report HTML references Plotly CDN resources; an offline browser may not render
  every interactive report even if the local server is healthy.
- The map uses external OpenStreetMap/Esri sources for basemaps. Their network
  availability is separate from your own S3 tile processing.
- Some existing lint findings predate these deployment instructions. Run
  `npm run build`, type checks as needed, and application acceptance tests;
  do not assume successful lint alone proves the deployed services work.

## 21. Final handoff checklist

- [ ] The incoming administrator can fetch/push the repository with their own credentials.
- [ ] A deployment commit and rollback reference are recorded.
- [ ] `.env` has real new/transferred values and is excluded from Git.
- [ ] Database role, ownership, authentication, and local-only listening are verified.
- [ ] Redis authentication and persistence are configured and tested.
- [ ] Both S3 buckets, Region, IAM policy, and both CORS rules are verified.
- [ ] CloudFront OAC policy and a real tile request are tested.
- [ ] GDAL/native Python imports and gdal2tiles work as the service user.
- [ ] Chrome/Kaleido renders a PNG as the service user.
- [ ] Dust weights/checksums/label mapping are supplied, or the unavailable feature is documented.
- [ ] Fresh tables are initialized, or restored tables are schema-checked.
- [ ] The intended first users/domains are approved.
- [ ] Both Celery queues have an active worker.
- [ ] API, workers, tunnel, PostgreSQL, and Redis are enabled at boot.
- [ ] Frontend root directory, environment, domain, and deployment are correct.
- [ ] A real small upload, multipart upload, analysis, report, and overlay work.
- [ ] Logout/reboot behavior has been tested in a maintenance window.
- [ ] Database/object/model/config backups and restoration have been tested.
- [ ] Production DNS cutover and retirement of old credentials are documented.

Repository references: [root README](../README.md),
[backend settings](../FastAPI/app/config.py),
[database models](../FastAPI/app/models.py),
[Celery routing](../FastAPI/app/celery_app.py),
[allowlist administration](../FastAPI/APPROVED_EMAILS.md),
[operating notes](operations.md), and [deployment overview](deployment.md).
