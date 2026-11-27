"""
Runtime Compatibility Shims for TraceOps AI.
Provides clean stdlib fallbacks when platform/OS Application Control policies restrict
binary C-extension DLLs (e.g. uuid_utils, xxhash, ormsgpack on Windows environments).
"""
import hashlib
import json
import sys
import types
import uuid
from typing import Any


class _MockUuidCompatModule(types.ModuleType):
    uuid7: Any


class _MockUuidModule(types.ModuleType):
    UUID: Any
    uuid4: Any
    uuid7: Any
    compat: _MockUuidCompatModule


class _MockOrmsgpack(types.ModuleType):
    packb: Any
    unpackb: Any
    MsgpackEncodeError: Any
    MsgpackDecodeError: Any
    OPT_NON_STR_KEYS: int
    OPT_SERIALIZE_NUMPY: int
    OPT_SERIALIZE_PYDANTIC: int
    OPT_PASSTHROUGH_DATACLASS: int
    OPT_PASSTHROUGH_DATETIME: int
    OPT_PASSTHROUGH_SUBCLASS: int

    def __getattr__(self, name: str) -> Any:
        if name.startswith("OPT_"):
            return 1
        raise AttributeError(f"No attribute {name}")


def install_runtime_shims() -> None:
    """Ensure uuid_utils, xxhash, and ormsgpack resolve cleanly to pure-python fallbacks."""
    # 1. xxhash shim
    if "xxhash" not in sys.modules or not hasattr(sys.modules["xxhash"], "xxh3_128_hexdigest"):
        m = types.ModuleType("xxhash")

        class MockXXH64:
            def __init__(self, data: Any = b"", seed: int = 0):
                raw = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
                self._m = hashlib.sha256(raw)

            def update(self, data: Any) -> None:
                raw = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
                self._m.update(raw)

            def intdigest(self) -> int:
                return int(self._m.hexdigest()[:16], 16)

            def hexdigest(self) -> str:
                return self._m.hexdigest()[:16]

            def digest(self) -> bytes:
                return self._m.digest()[:8]

        for name in ["xxh64", "xxh32", "xxh128", "xxh3_64", "xxh3_128"]:
            setattr(m, name, MockXXH64)

        def _hex(data: Any, seed: int = 0) -> str:
            raw = data.encode("utf-8") if isinstance(data, str) else data
            return hashlib.sha256(raw).hexdigest()[:32]

        def _int(data: Any, seed: int = 0) -> int:
            raw = data.encode("utf-8") if isinstance(data, str) else data
            return int(hashlib.sha256(raw).hexdigest()[:16], 16)

        def _dig(data: Any, seed: int = 0) -> bytes:
            raw = data.encode("utf-8") if isinstance(data, str) else data
            return hashlib.sha256(raw).digest()[:16]

        for prefix in ["xxh64", "xxh32", "xxh128", "xxh3_64", "xxh3_128"]:
            setattr(m, f"{prefix}_hexdigest", _hex)
            setattr(m, f"{prefix}_intdigest", _int)
            setattr(m, f"{prefix}_digest", _dig)

        sys.modules["xxhash"] = m
        sys.modules["xxhash._xxhash"] = m

    # 2. uuid_utils shim
    if "uuid_utils" not in sys.modules or not hasattr(sys.modules["uuid_utils"], "UUID"):
        mock_uuid = _MockUuidModule("uuid_utils")
        uuid7_fn = getattr(uuid, "uuid7", uuid.uuid4)
        mock_uuid.UUID = uuid.UUID
        mock_uuid.uuid4 = uuid.uuid4
        mock_uuid.uuid7 = uuid7_fn

        mock_compat = _MockUuidCompatModule("uuid_utils.compat")
        mock_compat.uuid7 = uuid7_fn
        mock_uuid.compat = mock_compat

        sys.modules["uuid_utils"] = mock_uuid
        sys.modules["uuid_utils.compat"] = mock_compat
        sys.modules["uuid_utils._uuid_utils"] = mock_uuid

    # 3. ormsgpack shim
    if "ormsgpack" not in sys.modules or not hasattr(
        sys.modules["ormsgpack"], "OPT_PASSTHROUGH_DATACLASS"
    ):
        mock_ormsgpack = _MockOrmsgpack("ormsgpack")

        def mock_packb(o: Any, **kwargs: Any) -> bytes:
            return json.dumps(o, default=str).encode("utf-8")

        def mock_unpackb(b: bytes, **kwargs: Any) -> Any:
            return json.loads(b.decode("utf-8"))

        mock_ormsgpack.packb = mock_packb
        mock_ormsgpack.unpackb = mock_unpackb
        mock_ormsgpack.MsgpackEncodeError = ValueError
        mock_ormsgpack.MsgpackDecodeError = ValueError
        mock_ormsgpack.OPT_NON_STR_KEYS = 1
        mock_ormsgpack.OPT_SERIALIZE_NUMPY = 2
        mock_ormsgpack.OPT_SERIALIZE_PYDANTIC = 4
        mock_ormsgpack.OPT_PASSTHROUGH_DATACLASS = 8
        mock_ormsgpack.OPT_PASSTHROUGH_DATETIME = 16
        mock_ormsgpack.OPT_PASSTHROUGH_SUBCLASS = 32

        sys.modules["ormsgpack"] = mock_ormsgpack
        sys.modules["ormsgpack.ormsgpack"] = mock_ormsgpack


install_runtime_shims()
