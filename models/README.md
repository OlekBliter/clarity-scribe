# Models

This folder holds the speech recognition models used by clarity-scribe.

## Vosk

Model: `vosk-model-small-uk-v3-small` (Ukrainian, small)

### Installation

1. Download the model from https://alphacephei.com/vosk/models (`vosk-model-small-uk-v3-small`).
2. Unzip it into this folder so that you end up with the path:

   ```
   models/vosk-model-small-uk-v3-small/
   ```

3. Make sure the path is set in your `.env` file:

   ```
   VOSK_MODEL_DIR=models/vosk-model-small-uk-v3-small
   ```

### Expected layout

```
models/
├── README.md
└── vosk-model-small-uk-v3-small/
    ├── am/
    ├── conf/
    ├── graph/
    ├── ivector/
    └── COPYING
```

## Attribution and license

The Vosk models are created and distributed by **Alpha Cephei Inc.** (https://alphacephei.com/vosk/), the authors of the Vosk speech recognition toolkit, and are licensed under the **Apache License 2.0** (https://www.apache.org/licenses/LICENSE-2.0).

Credits for the training data and other third-party components are listed in the model's `COPYING` file and in [`THIRDPARTY_LICENSES.txt`](../THIRDPARTY_LICENSES.txt) in the repository root.

