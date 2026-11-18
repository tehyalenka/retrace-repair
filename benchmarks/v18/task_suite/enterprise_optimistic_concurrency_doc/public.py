import unittest
from document_store import DocumentStore, PreconditionFailedError

class Public(unittest.TestCase):
    def test_update_with_matching_etag(self):
        store = DocumentStore()
        doc = store.create("user-1", {"name": "Alice", "role": "engineer"})
        etag1 = doc["etag"]

        updated = store.update("user-1", {"role": "architect"}, if_match_etag=etag1)
        self.assertEqual(updated["data"]["role"], "architect")
        self.assertEqual(updated["revision"], 2)
        self.assertNotEqual(updated["etag"], etag1)

    def test_mismatched_etag_raises_precondition_failed_and_does_not_mutate(self):
        store = DocumentStore()
        doc = store.create("user-1", {"name": "Alice", "role": "engineer"})

        with self.assertRaises(PreconditionFailedError):
            store.update("user-1", {"role": "director"}, if_match_etag="stale-etag-999")

        # Document must remain completely unchanged
        current = store.get("user-1")
        self.assertEqual(current["data"]["role"], "engineer")
        self.assertEqual(current["revision"], 1)
