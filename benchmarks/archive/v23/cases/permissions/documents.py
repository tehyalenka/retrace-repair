class DocumentStore:
    def __init__(self, documents):
        self.documents = dict(documents)
    def get(self, document_id):
        return self.documents.get(document_id)
