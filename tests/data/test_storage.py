from pathlib import Path

import pytest

from sales_insights.data.loader import load_orders
from sales_insights.data.schema import SchemaError
from sales_insights.data.storage import LocalStorage, Storage, StorageError


@pytest.fixture
def root(tmp_path):
    """A storage folder with two files and one sub-folder, next to a file outside it."""
    folder = tmp_path / "store"
    folder.mkdir()
    (folder / "b.csv").write_bytes(b"second")
    (folder / "a.csv").write_bytes(b"first")
    (folder / "nested").mkdir()
    (folder / "nested" / "c.csv").write_bytes(b"third")
    (tmp_path / "secret.txt").write_bytes(b"do not read")
    return folder


@pytest.fixture
def storage(root):
    return LocalStorage(root)


# --- reading, existence, listing --------------------------------------------------------


def test_read_returns_the_file_content_as_bytes(storage):
    assert storage.read("a.csv") == b"first"


def test_read_works_in_a_sub_folder(storage):
    assert storage.read("nested/c.csv") == b"third"


def test_exists_is_true_for_a_file_and_false_otherwise(storage):
    assert storage.exists("a.csv") is True
    assert storage.exists("nope.csv") is False
    assert storage.exists("nested") is False


def test_list_returns_sorted_file_names_without_folders(storage):
    assert storage.list() == ["a.csv", "b.csv"]


def test_list_of_an_empty_folder_is_empty(tmp_path):
    assert LocalStorage(tmp_path).list() == []


def test_missing_file_raises_file_not_found(storage):
    with pytest.raises(FileNotFoundError, match="nope.csv"):
        storage.read("nope.csv")


def test_reading_a_folder_raises_file_not_found(storage):
    with pytest.raises(FileNotFoundError):
        storage.read("nested")


# --- names that escape the root ---------------------------------------------------------


@pytest.mark.parametrize("name", ["../secret.txt", "nested/../../secret.txt", ".."])
def test_parent_folder_names_are_refused(storage, name):
    with pytest.raises(StorageError):
        storage.read(name)
    with pytest.raises(StorageError):
        storage.exists(name)


def test_absolute_paths_are_refused(storage, tmp_path):
    with pytest.raises(StorageError):
        storage.read(str(tmp_path / "secret.txt"))


def test_a_name_with_a_null_byte_is_refused_as_a_storage_error(storage):
    with pytest.raises(StorageError):
        storage.read("a\x00b.csv")
    with pytest.raises(StorageError):
        storage.exists("a\x00b.csv")


@pytest.mark.parametrize("name", ["", "."])
def test_the_root_itself_is_not_a_file_name(storage, name):
    with pytest.raises(StorageError):
        storage.read(name)


def test_a_symbolic_link_pointing_outside_is_refused(root, storage, tmp_path):
    link = root / "link.txt"
    try:
        link.symlink_to(tmp_path / "secret.txt")
    except OSError:
        pytest.skip("symbolic links are not available here")
    with pytest.raises(StorageError):
        storage.read("link.txt")


def test_storage_error_is_a_value_error():
    assert issubclass(StorageError, ValueError)


# --- the interface ----------------------------------------------------------------------


def test_local_storage_satisfies_the_storage_protocol(storage):
    assert isinstance(storage, Storage)


def test_an_object_without_the_methods_is_not_a_storage():
    assert not isinstance("data/orders.csv", Storage)


# --- loading orders from a storage ------------------------------------------------------

SAMPLE_FOLDER = Path(__file__).resolve().parents[2] / "data"
ORDERS_CSV = (
    "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"
    "1000,2025-01-05,Book,Books,10.0,2,C1,France\n"
)


class InMemoryStorage:
    """A storage that keeps its files in a dictionary."""

    def __init__(self, files):
        self.files = files

    def read(self, name):
        if name not in self.files:
            raise FileNotFoundError(name)
        return self.files[name]

    def exists(self, name):
        return name in self.files

    def list(self):
        return sorted(self.files)


def test_loading_through_local_storage_matches_loading_by_path():
    by_storage = load_orders(LocalStorage(SAMPLE_FOLDER), "sample_orders.csv")
    by_path = load_orders(SAMPLE_FOLDER / "sample_orders.csv")
    assert len(by_storage) == 500
    assert by_storage.equals(by_path)


def test_an_in_memory_storage_satisfies_the_protocol():
    assert isinstance(InMemoryStorage({}), Storage)


def test_loading_from_an_in_memory_storage():
    orders = load_orders(InMemoryStorage({"o.csv": ORDERS_CSV.encode()}), "o.csv")
    assert orders["Revenue"].tolist() == [20.0]


def test_loading_a_missing_name_from_a_storage_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_orders(InMemoryStorage({}), "o.csv")


def test_empty_content_from_a_storage_raises_a_clear_error():
    with pytest.raises(SchemaError, match="empty"):
        load_orders(InMemoryStorage({"o.csv": b""}), "o.csv")


def test_a_storage_without_a_name_is_rejected():
    with pytest.raises(TypeError, match="file name is required"):
        load_orders(InMemoryStorage({"o.csv": b""}))


def test_a_name_without_a_storage_is_rejected():
    with pytest.raises(TypeError, match="together with a storage"):
        load_orders("data/sample_orders.csv", "sample_orders.csv")
