# clarity-scribe
An AI copilot for psychiatrists and psychotherapists that automatically analyzes a patient's speech and vocal biomarkers during an audio session, generating a ready-made medical note and medical record.

## Models

Models are not stored in the repository because of their size. Download them manually and place them in the `models/` folder.

### Vosk (speech recognition)

1. Download the model from https://alphacephei.com/vosk/models (`vosk-model-small-uk-v3-small`)
2. Unzip it into the `models/` folder so that you end up with the path:

```
   models/vosk-model-small-uk-v3-small/
```

3. Make sure the path is set in your `.env` file:

```
   VOSK_MODEL_PATH=models/vosk-model-small-uk-v3-small
```
