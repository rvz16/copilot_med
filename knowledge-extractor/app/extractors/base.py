from abc import ABC, abstractmethod

from app.models.canonical import CanonicalExtraction


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, transcript: str, language: str = "ru") -> CanonicalExtraction:
        raise NotImplementedError
