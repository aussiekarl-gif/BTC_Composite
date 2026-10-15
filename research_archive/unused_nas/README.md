# Retired NAS/container deployment (archived 16 October 2026)

The user confirmed that **Streamlit is the only active application deployment**. The former Synology/NAS container path was unused.

The original content of these four files is preserved here:

| Archived file | Former location on `main` |
|---|---|
| [publish_nas_image.yml](./publish_nas_image.yml) | `.github/workflows/publish_nas_image.yml` |
| [Dockerfile](./Dockerfile) | `Dockerfile` |
| [compose.nas.yaml](./compose.nas.yaml) | `compose.nas.yaml` |
| [dockerignore.txt](./dockerignore.txt) | `.dockerignore` |

These were archived **before** removal from the active `main` branch. They are no longer part of the live app or GitHub Actions deployment pipeline. GitHub's previously published GHCR container images are not automatically deleted by deleting a workflow.

## Active Streamlit deployment

The current app runs from `app.py` and `requirements.txt`, with configuration in `.streamlit/config.toml` and the versioned `engines/` modules. Portfolio persistence continues to use the existing implementation in `engines/shared/portfolio_store.py`.

The approved Wednesday BTC/VBTC Research paper scheduler is **not related to Docker or the NAS** and remains enabled. It runs on GitHub Actions, checks out the Research branch, and updates only forward-paper Research evidence.

Nothing in this archive changes BTC risk scores, model versions, allocation calculations, portfolio storage, GitHub data sources, or frozen paper-trading parameters.

To restore a container-based deployment in the future, assess these archived files against the then-current Streamlit dependencies; do not blindly republish an outdated image.
