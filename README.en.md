# Music Eval

[中文文档](README.md)

A local CPU workbench for evaluating and comparing generated music. Import existing audio and prompts, inspect individual metrics, compare tracks under the same prompt, and optionally collect anonymous A/B preferences. Audio and prompts stay on your machine.

**Status: 0.1.0, unreleased.** Windows is the validated platform for the full model stack. Original project code is MIT licensed; third-party models and audio have separate terms. SongEval's upstream LICENSE and README contain inconsistent license statements: its integration remains restricted to non-commercial research pending clarification. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Quick start

Install Git, [uv](https://docs.astral.sh/uv/) and Node.js 22 LTS, then open PowerShell:

```powershell
git clone https://github.com/xiaotianming/music-eval.git
cd music-eval

# Core app, audio diagnostics and comparison; no model download required
./scripts/setup.ps1
./scripts/start.ps1
```

Open <http://127.0.0.1:8000> and load the synthetic demo to try the workflow. Import your generated tracks to compare models.

To enable optional CPU models:

```powershell
./scripts/setup.ps1 -Models
./scripts/setup-songeval.ps1
./scripts/setup-fad.ps1
./.venv/Scripts/python.exe scripts/download_models.py clap translation muq fad_clap roberta
```

SongEval and FAD use separate environments. Do not install their dependency stacks into the core environment. Download pinned assets and test the required metrics once before enabling offline mode. FFmpeg is supplied through `imageio-ffmpeg`.

## Metrics and limitations

- **Audio diagnostics:** duration, silence, near-full-scale samples, loudness, channels and non-finite values. Use these measurements to locate audio problems.
- **CLAP:** music-text similarity across contiguous 10-second windows. Chinese prompts are translated locally, with editable scoring text. Similarity is not a percentage of instructions satisfied.
- **SongEval:** full-song aesthetic predictions. Instrumental evaluation is opt-in and exploratory; vocal naturalness is not applicable.
- **FAD:** distribution distance between generated and reference collections. Choose reference music that matches your evaluation task.
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

Run the app from a source checkout. CI covers Windows/Linux core tests and the frontend build; the full model installers target Windows. The frontend's `private: true` setting prevents accidental npm publication.

## Documentation

The detailed documentation is currently in Chinese:

- [Dependency management and offline assets](docs/dependencies.md)
- [Architecture](docs/architecture.md) and [HTTP API](docs/api.md)
- [Evaluation protocol](docs/protocol.md) and [recorded validation](docs/validation.md)
- [Contributing](CONTRIBUTING.md), [security policy](SECURITY.md), [release checklist](docs/releasing.md)
- [Known dependency security status](docs/security-status.md)

The research model stack pins Transformers 4.51.3, which has known security advisories. Use trusted model assets and keep the service on localhost. Migration work is tracked in the [security status](docs/security-status.md).
