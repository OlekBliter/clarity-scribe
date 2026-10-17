from pathlib import Path

class FileReader:
    def __init__(self, path: str | Path, encoding: str = 'utf-8'):
        self.path = Path(path)
        self.encoding = encoding

    def read(self) -> str:
        return self.path.read_text(encoding=self.encoding)