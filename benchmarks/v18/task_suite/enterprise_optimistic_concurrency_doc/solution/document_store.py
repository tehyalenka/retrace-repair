import hashlib
import json
import copy

class PreconditionFailedError(Exception):
    pass

class DocumentStore:
    def __init__(self):
        self.docs = {}

    def _calc_etag(self, revision, data):
        content = json.dumps({"rev": revision, "data": data}, sort_keys=True)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def create(self, doc_id, data):
        if not doc_id or not isinstance(doc_id, str):
            raise ValueError("doc_id must be non-empty string")
        if not isinstance(data, dict):
            raise ValueError("data must be a dictionary")
        if doc_id in self.docs:
            raise ValueError(f"Document {doc_id} already exists")

        revision = 1
        data_copy = copy.deepcopy(data)
        etag = self._calc_etag(revision, data_copy)
        self.docs[doc_id] = {
            "doc_id": doc_id,
            "data": data_copy,
            "revision": revision,
            "etag": etag
        }
        return copy.deepcopy(self.docs[doc_id])

    def get(self, doc_id):
        if doc_id not in self.docs:
            raise KeyError(f"Document {doc_id} not found")
        return copy.deepcopy(self.docs[doc_id])

    def update(self, doc_id, patch_data, if_match_etag):
        if doc_id not in self.docs:
            raise KeyError(f"Document {doc_id} not found")
        if not isinstance(patch_data, dict):
            raise ValueError("patch_data must be a dictionary")
        if not if_match_etag or not isinstance(if_match_etag, str):
            raise ValueError("if_match_etag must be non-empty string")

        current = self.docs[doc_id]
        if current["etag"] != if_match_etag:
            raise PreconditionFailedError(
                f"ETag mismatch for doc '{doc_id}': expected {if_match_etag}, but current is {current['etag']}"
            )

        # Atomic update with state isolation
        new_data = copy.deepcopy(current["data"])
        new_data.update(copy.deepcopy(patch_data))
        new_rev = current["revision"] + 1
        new_etag = self._calc_etag(new_rev, new_data)

        self.docs[doc_id] = {
            "doc_id": doc_id,
            "data": new_data,
            "revision": new_rev,
            "etag": new_etag
        }
        return copy.deepcopy(self.docs[doc_id])
