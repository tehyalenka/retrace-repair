from directory import Directory
from documents import DocumentStore

class PermissionService:
    def __init__(self, directory, store):
        self.directory = directory
        self.store = store

    def can_access(self, user_id, document_id):
        raise NotImplementedError
