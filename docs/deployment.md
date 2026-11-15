# Deployment

This page explains how to run the project in a container: the dashboard, the command line, the settings it reads and what a deployment on a server or a cloud platform needs. To install it without a container, see the [README](../README.md#quick-start).

## The image

The `Dockerfile` at the root builds one image, `sales-insights`, that holds both interfaces:

- a slim Python 3.12 base, with the package and its `dashboard` extra only (no test or lint tools);
- the sample file `data/sample_orders.csv` and the Streamlit settings of `.streamlit/` (the 50 MB upload limit);
- a user without privileges (`app`, uid 10001): nothing in the container runs as root;
- the dashboard on port 8501 as the default command, and a health check on Streamlit's `/_stcore/health`.

`.dockerignore` keeps the rest out of the build: `.env`, `.git`, the tests, the docs, caches and virtual environments. The key of the AI features is never in the image; it is given when the container starts.

## Running the dashboard

With Docker Compose, from the root of the project:

```bash
docker compose up --build
```

Then open `http://localhost:8501`. `docker-compose.yml` reads `.env` when there is one (see [the settings](#settings)), runs the container with a read-only file system (only `/tmp` can be written) and without any Linux capability (`cap_drop: ALL`), and restarts it unless you stop it.

Without Compose:

```bash
docker build -t sales-insights .
docker run --rm -p 8501:8501 --env-file .env sales-insights
```

Leave out `--env-file .env` to run with the AI features switched off.

## Running the command line

The same image runs `sales-insights`; put the command after the image name:

```bash
docker run --rm sales-insights sales-insights -T data/sample_orders.csv
docker run -d --name check --read-only --tmpfs /tmp --cap-drop ALL -p 8501:8501 sales-insights
curl http://localhost:8501/_stcore/health             # ok
docker rm -f check
```

These checks were run on the image: the user is 10001, `/app` holds only the source, the sample file, the settings, `README.md`, `LICENSE` and `pyproject.toml`, the total is the one of the command line without Docker (`261333.44` on the sample file), and with a read-only file system and no capability the health check answers `ok` and Docker reports the container healthy.

To use your own file, mount its folder, read-only:

```bash
docker run --rm -v "$PWD/my-data:/data:ro" sales-insights sales-insights --by country /data/orders.csv
```

`--ask` needs the settings too: add `--env-file .env`. The exit codes are those of [the command-line reference](cli.md) (0, or 84 for a usage or data error).

## Settings

The container reads the variables of [`.env.example`](../.env.example), which are explained in [the AI guide](ai.md#switching-the-ai-on-or-off):

| Variable | Needed for |
|----------|------------|
| `SALES_AI_PROVIDER` | The written insights, the Ask tab and `--ask` |
| `SALES_AI_MODEL` | The same |
| `SALES_AI_API_KEY` | The same; empty means switched off |
| `SALES_AI_MAX_CALLS` | The limit of calls of one session (20 by default) |

Everything else works with none of them: the cards, the charts, the forecast and the facts. Pass the key at run time (`--env-file`, or the secrets of your platform), never with `ENV` in a Dockerfile or in a committed file.

## Deploying on a server or a cloud platform

The image runs on any platform that runs containers. What it needs:

- **A port.** The dashboard listens on 8501 on every interface of the container; map it, or tell the platform which port to route to.
- **The settings as secrets**, if the AI features are wanted.
- **One instance, or sticky sessions.** Streamlit keeps a session in the memory of the process that serves it: the history of the Ask tab, the written insights and the limit of calls of a session live there. Behind a load balancer, keep a visitor on the same instance.
- **Memory.** A file of a million orders takes about 0.5 GB to load; the upload limit (50 MB) keeps one upload under that. Give the container at least 1 GB.
- **The health check**: `/_stcore/health` answers `ok` when the dashboard is up.

What the project does not do, and a deployment open to the internet must add in front of it:

- **Authentication.** Anyone who reaches the page can use it, and every question to the model costs a call on your key. Put the dashboard behind a proxy or a platform feature that asks for a login.
- **HTTPS.** Streamlit serves plain HTTP; let the proxy or the platform end TLS.
- **A limit across sessions.** `SALES_AI_MAX_CALLS` limits one session; reloading the page starts a new one. A spending limit on the provider's side is the real cap.

## Checking an image

After a build, these commands check what the image promises:

```bash
docker run --rm sales-insights id -u                   # 10001: not root
docker run --rm sales-insights ls -a /app              # no .env, no tests
docker run --rm sales-insights sales-insights -T data/sample_orders.csv
docker run -d --name check --read-only --tmpfs /tmp --cap-drop ALL -p 8501:8501 sales-insights
curl http://localhost:8501/_stcore/health             # ok
docker rm -f check
```

These checks were run on the image: the user is 10001, `/app` holds only the source, the sample file, the settings, `README.md`, `LICENSE` and `pyproject.toml`, the total is the one of the command line without Docker (`261333.44` on the sample file), and with a read-only file system and no capability the health check answers `ok` and Docker reports the container healthy.
