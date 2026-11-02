from punctuators import PunctCapSegModelONNX
from functools import lru_cache

@lru_cache(maxsize=1)
def load_punctuation_model() -> PunctCapSegModelONNX:
  """
  Load the punctuation model and cache it.
 
  The first call loads the model (and, if the weights are not cached locally,
  downloads them from Hugging Face); every later call returns the same object.
  """
  return PunctCapSegModelONNX.from_pretrained("pcs_47lang")

def restore_punctuation(texts: list[str], model_i=None) -> list[str]:
  """
  Add punctuation and capitalization to each text.
 
  Args:
      texts: Lowercase texts without punctuation (e.g. Vosk segments).
          Empty or whitespace-only items are returned as empty strings.
      model_i: Loaded model to use. If None, the cached model from
          load_punctuation_model() is used.
 
  Returns:
      A list of strings, in the same order as `texts`. Each text is returned
      as its sentences joined by single spaces. The words themselves are not
      expected to change; the caller should verify the word count if it
      matters.
  """
  model = model_i if model_i is not None else load_punctuation_model()
  out = ["" if not (t and t.strip()) else t for t in texts]
  idx = [i for i, t in enumerate(texts) if t and t.strip()]

  if not idx:
    return texts

  for i, sentences in zip(idx, model.infer([texts[i] for i in idx])):
    out[i] = " ".join(sentences)
  return out
