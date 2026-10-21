# Music Eval

[中文文档](README.md)

A local CPU workbench for evaluating and comparing generated music. Import existing audio and prompts, inspect individual metrics, compare tracks under the same prompt, and optionally collect anonymous A/B preferences. Audio and prompts stay on your machine.

**Status: 0.1.0, unreleased.** Windows is the validated platform for the full model stack. Original project code is MIT licensed; third-party models and audio have separate terms. SongEval's upstream LICENSE and README contain inconsistent license statements: its integration remains restricted to non-commercial research pending clarification. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Quick start

Install Git, [uv](https://docs.astral.sh/uv/) and Node.js 22 LTS, clone the actual repository, and open PowerShell at its root:

```powershell
# Core app, audio diagnostics and comparison; no model download required
./scripts/setup.ps1
./scripts/start.ps1
```

Open <http://127.0.0.1:8000>. Use the synthetic demo to try the workflow. The demo is a software fixture, not evidence about any generation model's quality.

To enable optional CPU models:

```powershell
./scripts/setup.ps1 -Models
./scripts/setup-songeval.ps1
./scripts/setup-fad.ps1
./.venv/Scripts/python.exe scripts/download_models.py clap translation muq fad_clap roberta
```

SongEval and FAD use separate environments. Do not install their dependency stacks into the core environment. Download pinned assets and test the required metrics once before enabling offline mode. FFmpeg is supplied through `imageio-ffmpeg`.

## Metrics and limitations

- **Audio diagnostics:** duration, silence, near-full-scale samples, loudness, channels and non-finite values. These are diagnostics, not a perceptual quality score.
- **CLAP:** music-text similarity across contiguous 10-second windows. Chinese prompts are translated locally, with editable scoring text. Similarity is not a percentage of instructions satisfied.
- **SongEval:** full-song aesthetic predictions. Instrumental evaluation is opt-in and exploratory; vocal naturalness is not applicable.
- **FAD:** a batch-level distribution distance requiring an appropriate reference collection. It is not a per-track quality certificate or a universal pass/fail threshold.
- **Optional listening:** randomized anonymous A/B, ties and skips, reported separately from automatic metrics.

Jobs persist in SQLite, retain input snapshots, and support cancellation, retries and recovery. Reports use prompt-level equal weighting and shared-prompt bootstrap comparisons. No uncalibrated composite score is produced.

## Development

```powershell
uv sync --locked --extra dev
./.venv/Scripts/python.exe -m pytest -q
cd frontend
npm ci
npm run build
```

CI is configured for Windows/Linux core tests and frontend builds; this is not a claim that the full optional model stack is supported on Linux. The project is currently a source-checkout application, not a published PyPI package. Frontend `private: true` prevents accidental npm publication; it does not change the source license.

## Documentation

The detailed documentation is currently in Chinese:

- [Dependency management and offline assets](docs/dependencies.md)
- [Architecture](docs/architecture.md) and [HTTP API](docs/api.md)
- [Evaluation protocol](docs/protocol.md) and [recorded validation](docs/validation.md)
- [Contributing](CONTRIBUTING.md), [security policy](SECURITY.md), [release checklist](docs/releasing.md)
- [Known dependency security status](docs/security-status.md)

The frozen research model stack uses Transformers 4.51.3, which has known advisories and has not completed a major-version security migration. It is **not** advertised as audit-clean or safe for arbitrary untrusted checkpoints. The app is local-only and is not designed for public deployment.
