"""Typed input snapshots for the unchanged synchronous PAPER engine.

Call ``pin`` before handing a payload to a background writer. It detaches
ordinary mutable containers without hashing or serializing them. ``encode``
and ``canonical_bytes`` belong on the writer, not the dispatch thread.
``decode(encode(pin(value)))`` restores value and container-type semantics;
object alias identity is deliberately not part of the tape format.

Ownership contract for retained source objects
--------------------------------------------
Exact FeedSnapshot, PaperBook, and OfficialResult instances may be retained
without walking their large immutable trees on dispatch. They must originate
from the frozen source boundary: ``paper_feed.freeze_data`` builds fresh private
dicts behind its MappingProxyType objects and never exposes or mutates those
dicts. Frozen dataclass fields must also remain unchanged. A MappingProxyType
over a caller-owned, subsequently mutated dict does NOT satisfy this contract;
Python cannot distinguish those proxies. Generic kwargs proxies are copied,
not retained. The writer validates every retained subtree, rejects nested
dict/list or unsupported objects, and must mark the trace incomplete on error.
This rejects shallowly frozen synthetic sources with mutable descendants.

No Commander, ToolRack, executor, or other mutable engine-state object is an
accepted input type. There is no pickle, dynamic class import, or object hook.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
import math
from types import MappingProxyType
from typing import Any


SCHEMA = "tachyos.engine_inputs.codec.v1"
_TAG = "$tachyos"
_MAX_DEPTH = 128
_ATOMS = (type(None), bool, int, str)
_RETAINED_NAMES = frozenset(("FeedSnapshot", "PaperBook", "OfficialResult"))


class CodecError(ValueError):
    """An input cannot be captured or restored without changing its meaning."""


@dataclass(frozen=True, slots=True)
class _PinnedMapping(Mapping):
    kind: str
    entries: tuple

    def __iter__(self):
        return (key for key, _ in self.entries)

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, key):
        for original_key, value in self.entries:
            if original_key == key:
                return value
        raise KeyError(key)


@dataclass(frozen=True, slots=True)
class _PinnedSequence:
    kind: str
    values: tuple


@dataclass(frozen=True, slots=True)
class _PinnedDataclass:
    name: str
    values: tuple


@dataclass(frozen=True, slots=True)
class _RetainedSource:
    value: Any


_PINNED_TYPES = (_PinnedMapping, _PinnedSequence, _PinnedDataclass, _RetainedSource)


@lru_cache(maxsize=1)
def _registry():
    # Delayed imports let an offline runner select the verified source root
    # before loading the original engine. Importing these classes starts no I/O.
    from strategy_core.marketdata.kalshi_public import MarketInfo
    from strategy_core.paper_execution import OfficialResult, PaperBook, PriceLevel
    from strategy_core.paper_feed import FeedSnapshot
    from strategy_core.types import Side

    classes = (FeedSnapshot, MarketInfo, PaperBook, PriceLevel, OfficialResult)
    by_type = {cls: cls.__name__ for cls in classes}
    by_name = {cls.__name__: cls for cls in classes}
    names = {cls: tuple(field.name for field in fields(cls)) for cls in classes}
    if any(cls.__dataclass_params__.frozen is not True for cls in classes):
        raise CodecError("ORIGINAL_SOURCE_DATACLASS_NOT_FROZEN")
    return by_type, by_name, names, Side


def _number(value):
    if type(value) is float and not math.isfinite(value):
        raise CodecError("NONFINITE_FLOAT")
    if type(value) is Decimal and not value.is_finite():
        raise CodecError("NONFINITE_DECIMAL")
    return value


def _enter(value, active, depth):
    if depth > _MAX_DEPTH:
        raise CodecError("INPUT_DEPTH_LIMIT")
    identity = id(value)
    if identity in active:
        raise CodecError("CYCLIC_INPUT")
    active.add(identity)
    return identity


def pin(value: Any) -> Any:
    """Detach mutable input containers; reuse an already-pinned payload in O(1).

    Caller-owned mutable containers must not be concurrently written while
    this synchronous copy runs. Subsequent mutations cannot alter the pinned
    value. Only the documented frozen source instances are retained by reference.
    """
    return _pin(value, set(), 0)


def _pin(value, active, depth):
    cls = type(value)
    if cls in _ATOMS or cls in _PINNED_TYPES:
        return value
    if cls in (float, Decimal):
        return _number(value)
    identity = _enter(value, active, depth)
    try:
        if cls in (dict, MappingProxyType):
            return _PinnedMapping("dict" if cls is dict else "mappingproxy", tuple(
                (_pin(key, active, depth + 1), _pin(item, active, depth + 1))
                for key, item in value.items()))
        if cls in (list, tuple):
            return _PinnedSequence("list" if cls is list else "tuple", tuple(
                _pin(item, active, depth + 1) for item in value))
        by_type, _, field_names, side = _registry()
        if cls is side:
            return value
        name = by_type.get(cls)
        if name in _RETAINED_NAMES:
            return _RetainedSource(value)
        if name is not None:
            return _PinnedDataclass(name, tuple(
                (name, _pin(getattr(value, name), active, depth + 1))
                for name in field_names[cls]))
        raise CodecError("UNSUPPORTED_INPUT_TYPE:" + cls.__name__)
    finally:
        active.remove(identity)


def pin_call(method: str, args: dict) -> Mapping:
    """Pin the exact supplied arguments without filling defaults or using time."""
    if type(method) is not str or not method:
        raise CodecError("CALL_METHOD_REQUIRED")
    if type(args) is not dict or any(type(key) is not str for key in args):
        raise CodecError("CALL_ARGUMENTS_REQUIRE_STRING_KEYED_DICT")
    return pin({"method": method, "arguments": args})


def encode(value: Any, *, snapshot_encoder=None) -> Any:
    """Return a JSON-safe typed tree; validate all deferred source references.

    Plain values are accepted for direct use, but enqueueing a mutable value
    and waiting until this function runs does not capture its dispatch-time
    contents. Asynchronous producers must enqueue ``pin(value)`` instead.
    """
    pinned = pin(value)
    snapshots = None
    if snapshot_encoder is not None and type(pinned) is _PinnedMapping:
        call = pinned.get("call")
        if type(call) is _PinnedMapping and call.get("method") == "process":
            arguments = call.get("arguments")
            if type(arguments) is _PinnedMapping:
                feed = arguments.get("feed")
                source = feed.value if type(feed) is _RetainedSource else None
                snapshots = (arguments, source, snapshot_encoder)
    return _encode(pinned, set(), 0, snapshots)


def _encode(value, active, depth, snapshots=None):
    cls = type(value)
    if cls in _ATOMS:
        return value
    if cls is float:
        return _number(value)
    if cls is Decimal:
        return {_TAG: "Decimal", "value": str(_number(value))}
    if cls is _registry()[3]:
        return {_TAG: "Side", "value": value.value}
    identity = _enter(value, active, depth)
    try:
        if cls is _PinnedMapping:
            def item_value(key, item):
                if (snapshots is not None and value is snapshots[0]
                        and key == "historical_candles" and type(item) is _PinnedSequence):
                    return snapshots[2]("historical_candles", item.kind, item.values,
                                        lambda row: _encode(row, active, depth + 2), False)
                return _encode(item, active, depth + 1, snapshots)
            return {_TAG: value.kind, "items": [
                [_encode(key, active, depth + 1, snapshots), item_value(key, item)]
                for key, item in value.entries]}
        if cls is _PinnedSequence:
            return {_TAG: value.kind, "items": [
                _encode(item, active, depth + 1, snapshots) for item in value.values]}
        if cls is _PinnedDataclass:
            return {_TAG: "dataclass", "name": value.name, "fields": [
                [name, _encode(item, active, depth + 1, snapshots)] for name, item in value.values]}
        if cls is _RetainedSource:
            return _encode_source(value.value, active, depth + 1, snapshots)
        raise CodecError("UNPINNED_INPUT_TYPE:" + cls.__name__)
    finally:
        active.remove(identity)


def _encode_source(value, active, depth, snapshots=None):
    """Serialize a retained source only if its entire tree is immutable."""
    cls = type(value)
    if cls in _ATOMS:
        return value
    if cls is float:
        return _number(value)
    if cls is Decimal:
        return {_TAG: "Decimal", "value": str(_number(value))}
    by_type, _, field_names, side = _registry()
    if cls is side:
        return {_TAG: "Side", "value": value.value}
    if cls in (dict, list):
        raise CodecError("RETAINED_SOURCE_MUTABLE:" + cls.__name__)
    identity = _enter(value, active, depth)
    try:
        if cls is tuple:
            return {_TAG: "tuple", "items": [
                _encode_source(item, active, depth + 1, snapshots) for item in value]}
        if cls is MappingProxyType:
            return {_TAG: "mappingproxy", "items": [
                [_encode_source(key, active, depth + 1, snapshots),
                 _encode_source(item, active, depth + 1, snapshots)] for key, item in value.items()]}
        if cls in by_type:
            def field_value(name):
                item = getattr(value, name)
                if (snapshots is not None and value is snapshots[1]
                        and by_type[cls] == "FeedSnapshot" and name == "geometry_rows"
                        and type(item) is tuple):
                    return snapshots[2]("geometry_rows", "tuple", item,
                                        lambda row: _encode_source(row, active, depth + 2), True)
                return _encode_source(item, active, depth + 1, snapshots)
            return {_TAG: "dataclass", "name": by_type[cls], "fields": [
                [name, field_value(name)]
                for name in field_names[cls]]}
        raise CodecError("RETAINED_SOURCE_UNSUPPORTED:" + cls.__name__)
    finally:
        active.remove(identity)


def canonical_bytes(value: Any) -> bytes:
    """Encode and serialize an original/pinned value, not an already-encoded tree.

    Mapping entries are represented as lists, preserving insertion order even
    though JSON wrapper keys are sorted. This is important for exact call and
    inventory iteration semantics.
    """
    return json.dumps(encode(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def decode(value: Any) -> Any:
    """Restore only explicitly allowed input types from an encoded JSON tree."""
    return _decode(value, set(), 0, False)


def _decode(value, active, depth, immutable):
    cls = type(value)
    if cls in _ATOMS:
        return value
    if cls is float:
        return _number(value)
    if cls is not dict or type(value.get(_TAG)) is not str:
        raise CodecError("ENCODED_TYPE_TAG_REQUIRED")
    identity = _enter(value, active, depth)
    try:
        tag = value[_TAG]
        if tag in ("Decimal", "Side"):
            if set(value) != {_TAG, "value"} or type(value["value"]) is not str:
                raise CodecError("ENCODED_SCALAR_INVALID")
            try:
                restored = Decimal(value["value"]) if tag == "Decimal" else _registry()[3](value["value"])
            except (InvalidOperation, ValueError) as exc:
                raise CodecError("ENCODED_SCALAR_INVALID") from exc
            if tag == "Decimal" and str(_number(restored)) != value["value"]:
                raise CodecError("ENCODED_DECIMAL_NOT_CANONICAL")
            return restored
        if tag in ("list", "tuple", "dict", "mappingproxy"):
            if set(value) != {_TAG, "items"} or type(value["items"]) is not list:
                raise CodecError("ENCODED_CONTAINER_INVALID")
            if immutable and tag in ("list", "dict"):
                raise CodecError("RETAINED_SOURCE_MUTABLE:" + tag)
            if tag in ("list", "tuple"):
                items = [_decode(item, active, depth + 1, immutable) for item in value["items"]]
                return items if tag == "list" else tuple(items)
            restored = {}
            for pair in value["items"]:
                if type(pair) is not list or len(pair) != 2:
                    raise CodecError("ENCODED_MAPPING_PAIR_INVALID")
                key = _decode(pair[0], active, depth + 1, immutable)
                item = _decode(pair[1], active, depth + 1, immutable)
                try:
                    if key in restored:
                        raise CodecError("ENCODED_MAPPING_DUPLICATE_KEY")
                    restored[key] = item
                except TypeError as exc:
                    raise CodecError("ENCODED_MAPPING_UNHASHABLE_KEY") from exc
            return restored if tag == "dict" else MappingProxyType(restored)
        if tag == "dataclass":
            if (set(value) != {_TAG, "name", "fields"} or type(value["name"]) is not str
                    or type(value["fields"]) is not list):
                raise CodecError("ENCODED_DATACLASS_INVALID")
            _, by_name, field_names, _ = _registry()
            original = by_name.get(value["name"])
            if original is None:
                raise CodecError("ENCODED_DATACLASS_NOT_ALLOWED")
            supplied = value["fields"]
            if (any(type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str
                    for pair in supplied)
                    or tuple(pair[0] for pair in supplied) != field_names[original]):
                raise CodecError("ENCODED_DATACLASS_FIELDS_MISMATCH")
            required_immutable = immutable or value["name"] in _RETAINED_NAMES
            kwargs = {name: _decode(item, active, depth + 1, required_immutable)
                      for name, item in supplied}
            return original(**kwargs)
        raise CodecError("ENCODED_TYPE_NOT_ALLOWED:" + tag)
    finally:
        active.remove(identity)
