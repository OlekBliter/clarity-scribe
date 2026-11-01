# Models
 
This folder holds the machine learning models used by clarity-scribe. Model files are never committed to Git (see `.gitignore`); every machine downloads them once.
 
| Model | Used for | Env variable |
|---|---|---|
| Vosk `vosk-model-small-uk-v3-small` | Ukrainian speech recognition | `VOSK_MODEL_DIR` |
| GLiNER `gliner_multi-v2.1` | Finding names, places and organisations in transcripts (privacy NER) | `GLINER_MODEL_DIR` |
| `punct_cap_seg_47_language` (optional) | Restoring punctuation and capitalization in transcripts (`punctuate=True`) | `PUNCTUATION_MODEL_DIR` |
 
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
 
## GLiNER (privacy NER)
 
Model: `urchade/gliner_multi-v2.1` (multilingual zero-shot NER) together with the tokenizer and config of its encoder `microsoft/mdeberta-v3-base`. The service never downloads anything: both must be placed here by hand.
 
### Installation
 
1. Open https://huggingface.co/urchade/gliner_multi-v2.1, tab **Files and versions**, and download all files into `models/gliner_multi-v2.1/`.
2. Open https://huggingface.co/microsoft/mdeberta-v3-base, tab **Files and versions**, and download only the tokenizer and config files into `models/gliner_multi-v2.1/backbone/`:
   `config.json`, `tokenizer_config.json`, `spm.model`, `added_tokens.json`, `special_tokens_map.json` (and `tokenizer.json` if present). The encoder weights are not needed: they are already inside the GLiNER model.
3. Open `models/gliner_multi-v2.1/gliner_config.json` and replace the value of `model_name` (`microsoft/mdeberta-v3-base`) with the local encoder folder:
```
   "model_name": "models/gliner_multi-v2.1/backbone"
```
 
   The path is relative to the project root, so run the service from there (or use an absolute path).
4. Make sure the path is set in your `.env` file:
 
```
   GLINER_MODEL_DIR=models/gliner_multi-v2.1
```
 
## Punctuation and capitalization (optional)
 
Model: `1-800-BAD-CODE/punct_cap_seg_47_language` (ONNX), run through the `punctuators` package (`PunctCapSegModelONNX`; the package's short name for this model is `pcs_47lang`).
 
The Vosk recognizer outputs lowercase text without punctuation. This model adds punctuation (`. , ?`), capitalization (true-casing) and sentence boundaries to such text. It is used only when a transcription is requested with `punctuate=True`; without that flag the model is neither imported nor loaded, and it is not needed.
 
Notes:
 
- The model card lists Ukrainian (`uk`) among its 47 languages, but the card gives no quality figures for Ukrainian. Check the output on your own recordings before relying on it.
- Words are not expected to change (the model only labels the text), and the pipeline keeps the original segment text if the number of words changes. Timestamps are never modified.
- The model runs on the CPU (about 260 MB of RAM, about 3 ms per word in our measurements). The `punctuators` package depends on `torch`, `onnxruntime`, `sentencepiece`, `huggingface-hub`, `omegaconf` and `numpy`.
- By default `punctuators` downloads the weights from Hugging Face on first use. The service must not do that, so the weights are placed here by hand and loaded from `PUNCTUATION_MODEL_DIR`.
### Installation
 
1. Install the `punctuators` package (see `requirements/audio.txt`).
2. Download three files from https://huggingface.co/1-800-BAD-CODE/punct_cap_seg_47_language (tab **Files and versions**) into `models/punct_cap_seg_47_language/`:
   - `punct_cap_seg_47lang.onnx`
   - `spe_unigram_64k_lowercase_47lang.model`
   - `config.yaml`
   Or download them with a short script (run it from the project root):
```
   python -c "from huggingface_hub import hf_hub_download as d; [d('1-800-BAD-CODE/punct_cap_seg_47_language', f, local_dir='models/punct_cap_seg_47_language') for f in ('punct_cap_seg_47lang.onnx', 'spe_unigram_64k_lowercase_47lang.model', 'config.yaml')]"
```
 
3. Make sure the path is set in your `.env` file:
```
   PUNCTUATION_MODEL_DIR=models/punct_cap_seg_47_language
```
 
## Expected layout
 
```
models/
├── README.md
├── THIRDPARTY_LICENSES.txt
├── vosk-model-small-uk-v3-small/
│   ├── am/
│   ├── conf/
│   ├── graph/
│   ├── ivector/
│   └── COPYING
├── gliner_multi-v2.1/
│   ├── gliner_config.json
│   ├── pytorch_model.bin
│   └── backbone/
│       ├── config.json
│       ├── tokenizer_config.json
│       └── spm.model
└── punct_cap_seg_47_language/        (optional, for punctuate=True)
    ├── punct_cap_seg_47lang.onnx
    ├── spe_unigram_64k_lowercase_47lang.model
    └── config.yaml
```
 
## Attribution and license
 
The Vosk models are created and distributed by **Alpha Cephei Inc.** (https://alphacephei.com/vosk/), the authors of the Vosk speech recognition toolkit, and are licensed under the **Apache License 2.0** (https://www.apache.org/licenses/LICENSE-2.0).
 
GLiNER models are created by Urchade Zaratiana, Nadi Tomeh, Pierre Holat and Thierry Charnois. (https://github.com/urchade/GLiNER); `gliner_multi-v2.1` is published at https://huggingface.co/urchade/gliner_multi-v2.1 and is licensed under the **Apache License 2.0** (https://www.apache.org/licenses/LICENSE-2.0). The `mdeberta-v3-base` encoder is created by Microsoft (https://huggingface.co/microsoft/mdeberta-v3-base) and is licensed under the **MIT license**.
 
The punctuation model `punct_cap_seg_47_language` is published by `1-800-BAD-CODE` at https://huggingface.co/1-800-BAD-CODE/punct_cap_seg_47_language and is licensed under the **Apache License 2.0** (https://www.apache.org/licenses/LICENSE-2.0).
 
Check the license shown on each model page and keep it in sync with [`THIRDPARTY_LICENSES.txt`](THIRDPARTY_LICENSES.txt).
 
Credits for the training data and other third-party components are listed in the model's `COPYING` file.
