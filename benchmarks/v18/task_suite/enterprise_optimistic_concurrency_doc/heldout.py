import unittest
from document_store import DocumentStore, PreconditionFailedError

class Heldout(unittest.TestCase):
    def test_defensive_copying_isolation(self):
        store = DocumentStore()
        doc = store.create("d1", {"items": [1, 2, 3]})
        
        # Mutating caller copy must NOT mutate store internal state
        doc["data"]["items"].append(999)
        refetch = store.get("d1")
        self.assertEqual(refetch["data"]["items"], [1, 2, 3])

    def test_missing_document_raises_key_error(self):
        store = DocumentStore()
        with self.assertRaises(KeyError):
            store.get("nonexistent")
        with self.assertRaises(KeyError):
            store.update("nonexistent", {"a": 1}, if_match_etag="abc")

    def test_invalid_parameters_raise_value_error(self):
        store = DocumentStore()
        with self.assertRaises(ValueError):
            store.create("", {"a": 1})
        with self.assertRaises(ValueError):
            store.create("d2", "not a dict")
        store.create("d3", {"a": 1})
        with self.assertRaises(ValueError):
            store.update("d3", "not a dict", if_match_etag="abc")
        with self.assertRaises(ValueError):
            store.update("d3", {"b": 2}, if_match_etag="")

    def test_sequential_concurrent_rejection(self):
        store = DocumentStore()
        d = store.create("d4", {"count": 0})
        etag0 = d["etag"]

        # First update succeeds
        u1 = store.update("d4", {"count": 1}, if_match_etag=etag0)
        self.assertEqual(u1["revision"], 2)

        # Second update trying to use stale etag0 must fail
        with self.assertRaises(PreconditionFailedError):
            store.update("d4", {"count": 2}, if_match_etag=etag0)
        
        # Final state check
        current = store.get("d4")
        self.assertEqual(current["data"]["count"], 1)
