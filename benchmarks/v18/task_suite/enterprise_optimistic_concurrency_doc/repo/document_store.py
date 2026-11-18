import hashlib
import json

class PreconditionFailedError(Exception):
    pass

class DocumentStore:
    def __init__(self):
        self.docs = {}

    def _calc_etag(self, revision, data):
        content = json.dumps({"rev": revision, "data": data}, sort_keys=True)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def create(self, doc_id, data):
        revision = 1
        etag = self._calc_etag(revision, data)
        self.docs[doc_id] = {"doc_id": doc_id, "data": dict(data), "revision": revision, "etag": etag}
        return dict(self.docs[doc_id])

    def get(self, doc_id):
        if doc_id not in self.docs:
            raise KeyError(f"Document {doc_id} not found")
        # Bug: returns internal reference instead of deep/independent copy
        return self.docs[doc_id]

    def update(self, doc_id, patch_data, if_match_etag):
        if doc_id not in self.docs:
            raise KeyError(f"Document {doc_id} not found")
        
        # Buggy repo: mutates data before verifying if_match_etag!
        self.docs[doc_id]["data"].update(patch_data)
        
        if self.docs[doc_id]["etag"] != if_match_etag:
            # Bug: already mutated! And doesn't rollback
            raise PreconditionFailedError("ETag mismatch")

        self.docs[doc_id]["revision"] += 1
        self.docs[doc_id]["etag"] = self._calc_etag(self.docs[doc_id]["revision"], self.docs[doc_id]["data"])
        return self.docs[doc_id]
