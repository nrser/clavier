from __future__ import annotations
from enum import IntEnum
from io import BytesIO
from socket import socket
import struct
from typing import (
    IO,
    Any,
    Callable,
    Iterable,
    Mapping,
    NamedTuple,
    Sequence,
    TypeVar,
)


class Tag(IntEnum):
    INT = 1
    FLOAT = 2
    STR = 3
    BYTES = 4
    LIST = 5
    MAP = 6


TRecord = TypeVar("TRecord", bound="Record")

TAG_LENGTH_STRUCT = struct.Struct("HH")
INT_STRUCT = struct.Struct("i")
FLOAT_STRUCT = struct.Struct("f")


class Record(NamedTuple):
    @classmethod
    def of(cls: type[TRecord], obj: object, _memo: tuple = ()) -> TRecord:
        match obj:
            case int(i):
                return cls(Tag.INT, INT_STRUCT.size, INT_STRUCT.pack(i))

            case float(f):
                return cls(Tag.FLOAT, FLOAT_STRUCT.size, FLOAT_STRUCT.pack(f))

            case str(s):
                b = bytes(s, encoding="utf-8")
                return cls(Tag.STR, len(b), b)

            case bytes(b):
                return cls(Tag.BYTES, len(b), b)

            case sequence if isinstance(sequence, Sequence):
                if sequence in _memo:
                    raise Exception("Circular reference")
                new_memo = (*_memo, sequence)
                records = tuple(cls.of(item, new_memo) for item in sequence)
                return cls(Tag.LIST, sum(r.size for r in records), records)

            case mapping if isinstance(mapping, Mapping):
                if mapping in _memo:
                    raise Exception("Circular reference")
                new_memo = (*_memo, mapping)
                records = []
                for key, value in mapping.items():
                    records.append(cls.of(key, new_memo))
                    records.append(cls.of(value, new_memo))
                return cls(
                    Tag.MAP, sum(r.size for r in records), tuple(records)
                )

        raise TypeError(f"can't create record from {type(obj)}: {obj!r}")

    @classmethod
    def read_from(cls: type[TRecord], io: IO[bytes]):
        header = io.read(TAG_LENGTH_STRUCT.size)
        tag, length = TAG_LENGTH_STRUCT.unpack(header)
        match tag:
            case Tag.INT:
                return INT_STRUCT.unpack(io.read(length))[0]
            case Tag.FLOAT:
                return FLOAT_STRUCT.unpack(io.read(length))[0]
            case Tag.STR:
                return io.read(length).decode("utf-8")
            case Tag.BYTES:
                return io.read(length)
            case Tag.LIST:
                end = io.tell() + length
                values = []
                while io.tell() < end:
                    values.append(cls.read_from(io))
                return values
            case Tag.MAP:
                end = io.tell() + length
                values = {}
                while io.tell() < end:
                    key = cls.read_from(io)
                    value = cls.read_from(io)
                    values[key] = value
                return values

        raise TypeError(f"unknown tag {tag!r}")

    @classmethod
    def parse(cls, data: bytes):
        return cls.read_from(BytesIO(data))

    tag: Tag
    length: int
    value: bytes | tuple[Record, ...]

    @property
    def size(self) -> int:
        """The total size (in bytes) that this record takes up on the wire,
        which is the header size (tag and length fields) plus the `length`.
        """
        return TAG_LENGTH_STRUCT.size + self.length

    def write_to(self, write: Callable[[bytes], Any]) -> None:
        write(TAG_LENGTH_STRUCT.pack(self.tag, self.length))

        if isinstance(self.value, bytes):
            write(self.value)
        else:
            for record in self.value:
                record.write_to(write)

    def to_bytes(self) -> bytes:
        bio = BytesIO()
        self.write_to(bio.write)
        return bio.getvalue()


def rt(obj):
    bio = BytesIO()
    rec = Record.of(obj)
    rec.write_to(bio.write)
    bio.seek(0)
    return Record.read_from(bio)
