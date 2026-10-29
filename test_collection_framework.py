import tempfile
import unittest
from pathlib import Path

from collection_framework import (
    Collection, DuplicateIdError, Field, Index, NotFoundError, ValidationError,
)


class CollectionTests(unittest.TestCase):
    def make_collection(self, path=None):
        return Collection(
            {"id": Field(str, required=True), "name": Field(str, required=True),
             "age": Field(int, required=True), "tags": Field(list),
             "metadata": Field(dict)},
            indexes=[Index("name", "hash"), Index("age", "ordered")],
            storage_path=path,
        )

    def test_crud_indexes_and_integrity(self):
        c = self.make_collection()
        c.insert({"id": "a", "name": "Ana", "age": 30, "tags": ["x"]})
        c.insert({"id": "b", "name": "Bia", "age": 24})
        self.assertEqual(c.find("name", "Ana")[0]["id"], "a")
        self.assertEqual([x["id"] for x in c.where("age", gte=25)], ["a"])
        c.update("a", {"age": 20, "metadata": {"ok": True}})
        self.assertEqual(c.get("a")["age"], 20)
        self.assertEqual([x["id"] for x in c.list(order_by="age")], ["a", "b"])
        self.assertTrue(c.check_integrity())
        c.delete("a")
        self.assertEqual(c.count(), 1)
        self.assertTrue(c.check_integrity())

    def test_natural_numeric_sort_and_pagination(self):
        c = self.make_collection()
        for i in [10, 2, 1]: c.insert({"id": str(i), "name": str(i), "age": i})
        self.assertEqual([r["age"] for r in c.list(order_by="age")], [1, 2, 10])
        self.assertEqual([r["age"] for r in c.list(order_by="age", offset=1, limit=1)], [2])

    def test_validation_and_duplicate(self):
        c = self.make_collection()
        with self.assertRaises(ValidationError): c.insert({"id": "a", "age": "trinta", "name": "Ana"})
        c.insert({"id": "a", "name": "Ana", "age": 30})
        with self.assertRaises(DuplicateIdError): c.insert({"id": "a", "name": "Ana", "age": 30})
        with self.assertRaises(ValidationError): c.insert({"id": "b", "name": "Bia", "age": 20, "extra": 1})

    def test_graph_relationships_and_cascade_edge_removal(self):
        c = self.make_collection()
        for rid in ["a", "b"]: c.insert({"id": rid, "name": rid, "age": 20})
        c.connect("a", "b")
        self.assertEqual(c.neighbors("a")[0]["id"], "b")
        c.delete("b")
        self.assertEqual(c.neighbors("a"), [])

    def test_json_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            c = self.make_collection(path)
            c.insert({"id": "a", "name": "Ana", "age": 30, "metadata": {"city": "SP"}})
            c2 = self.make_collection(path)
            self.assertEqual(c2.get("a")["metadata"]["city"], "SP")
            self.assertTrue(c2.check_integrity())

    def test_missing_record(self):
        c = self.make_collection()
        with self.assertRaises(NotFoundError): c.get("missing")


if __name__ == "__main__":
    unittest.main()
