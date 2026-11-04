# ClarityScribe

ClarityScribe is a local desktop application for analyzing therapy-session
audio, extracting speech biomarkers, anonymizing transcript data, and
generating clinical documents with Google Gemini. Audio, models, and the
database stay on the local machine; only configured LLM requests leave it.

## Local setup

The commands below are run from the repository root.

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

Install the requirements files in this order:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements\base.txt
python -m pip install -r requirements\audio.txt
python -m pip install -r requirements\biomarkers.txt
python -m pip install -r requirements\llm.txt
python -m pip install -r requirements\ner.txt
python -m pip install -r requirements\app.txt
```

### 3. Download local models

Model weights are intentionally not stored in Git. Download and place them
under `models\` as described in [models/README.md](models/README.md):

- Vosk Ukrainian model in `models\vosk-model-small-uk-v3-small\`;
- GLiNER model and its local `backbone\` in `models\gliner_multi-v2.1\`;
- optional punctuation model if punctuation restoration is enabled.

Keep the model directory structure intact. Do not commit weights or generated
model files.

### 4. Configure environment variables

Create a local `.env` from the template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

| Variable | Purpose |
|---|---|
| `CLARITYSCRIBE_DATA_DIR` | Root for `clarityscribe.db` and `audio\`; empty uses the platform default, such as `%APPDATA%\clarityscribe` on Windows. |
| `GEMINI_API_KEY` | Google Gemini API key for S3/S4. |
| `VOSK_MODEL_DIR` | Relative or absolute path to the Vosk model. |
| `GLINER_MODEL_DIR` | Relative or absolute path to the GLiNER model and `backbone\`. |

Never commit `.env` or paste the API key into tracked files.

### 5. Run from the repository root

Always start Python with the repository root as the working directory so
relative model paths and package imports resolve correctly:

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import src; print('ClarityScribe environment is ready')"
```

The application entrypoint is under active development in `src/app/`. When the
desktop entrypoint is available, launch it from this same repository root with
the project's documented `python -m ...` command.

## Repository rules

- Keep secrets in local `.env` files only.
- Keep model weights outside Git; only model documentation and third-party
  license files belong in `models\`.
- Keep runtime databases, WAL/SHM files, audio recordings, caches, and build
  artifacts outside Git.
