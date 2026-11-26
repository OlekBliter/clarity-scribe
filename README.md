# ClarityScribe

ClarityScribe is a desktop app that helps clinicians turn Ukrainian-language therapy recordings into clinical notes. Import a stereo recording, review the transcript alongside the audio, and check the generated drafts against what was said before approving them.

## From recording to reviewed notes

1. **Add a session.** Open a patient profile and import a stereo PCM WAV with one speaker per channel. By default, channel 0 is the clinician and channel 1 is the patient. If your recorder uses the opposite order, swap the channels in Settings before importing. Use 16- or 24-bit PCM when exporting from an audio editor.
2. **Review the drafts.** The first session produces an intake medical card and a SOAP note. Subsequent sessions produce a SOAP note. Open a source timestamp to inspect the transcript evidence, edit the draft, and save your changes. Approving a document makes it read-only.
3. **Track changes across visits.** After two approved sessions, open the dynamics screen to compare speech measures such as pause ratio and speech rate. The overview shows up to ten recent sessions. Select a chart to see its full history.
4. **Export a report.** The session, medical card, and dynamics screens each offer a PDF export.

The app processes one recording at a time. You can browse other patients while it runs and return through the progress banner. If generation is interrupted, choose **Continue processing** to resume from the saved recording. **Replace recording** starts over and discards the session’s drafts and saved edits.

## Where patient data goes

Audio, original transcripts, patient contacts, and reviewed documents are stored on the local computer. Transcription with Vosk, detection of identifying text with GLiNER, and speech measurements also run locally.

Document generation requires an internet connection to Google Gemini. Before generation, ClarityScribe replaces detected identifiers in the transcript with placeholders. The generation requests use this processed text and, for the SOAP note, speech measurements. The audio file and the local mapping used to restore identifiers stay on the computer.

## Try the demo

The demo opens with sample patients and sessions. It runs without model downloads or a Gemini key. Changes are kept in memory until you close the app.

From the repository root, run these commands in Windows PowerShell with Python 3.12 installed.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\base.txt -r requirements\app.txt
.\.venv\Scripts\python.exe -m src.app.main --stub
```

## Use your own recordings

**Install the processing dependencies.** After creating the environment above, run the following from the same directory.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements\audio.txt -r requirements\biomarkers.txt -r requirements\llm.txt -r requirements\ner.txt
```

**Install the local models.** Download the Ukrainian Vosk model and GLiNER weights, including the GLiNER backbone. The model guide lists the expected folder structure and the optional punctuation model. [Model setup](models/README.md)

**Configure the app.** On first setup, copy the environment template and edit the resulting `.env` file.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

| Setting | Purpose |
| --- | --- |
| `VOSK_MODEL_DIR` | Ukrainian speech recognition model, typically `models/vosk-model-small-uk-v3-small`. |
| `GLINER_MODEL_DIR` | Identifier detection model, typically `models/gliner_multi-v2.1`, with its local `backbone/`. |
| `CLARITYSCRIBE_DATA_DIR` | Optional location for `clarityscribe.db` and the `audio/` directory. The Windows default is `%APPDATA%\clarityscribe`. |
| `GEMINI_API_KEY` | Key for generating clinical drafts. You can also enter it in the app’s Settings and test the connection there. |

**Launch the app** with the local database.

```powershell
.\.venv\Scripts\python.exe -m src.app.main
```
