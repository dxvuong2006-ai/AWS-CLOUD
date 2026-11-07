from abc import ABC, abstractmethod


class StorageAdapter(ABC):

    @abstractmethod
    def generate_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in: int = 900,
    ) -> str:
        pass