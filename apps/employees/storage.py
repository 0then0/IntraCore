from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePendingPhotoStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=settings.PRIVATE_PHOTO_ROOT,
            base_url="/private-pending-photos/",
        )

    def private_exists(self, name: str) -> bool:
        return super().exists(name)

    def open(self, name: str, mode: str = "rb"):
        if self.private_exists(name):
            return super().open(name, mode)

        return default_storage.open(name, mode)

    def delete(self, name: str) -> None:
        super().delete(name)
        default_storage.delete(name)
