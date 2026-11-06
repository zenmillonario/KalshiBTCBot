"""Lossless previous-window references for two complete engine input snapshots.

This is a storage encoding, never a source sampler. Every CALL remains present.
Only process.feed.geometry_rows and process.historical_candles are eligible.
Every snapshot gives its full ordered membership through copy ranges and full
typed literal rows; references address only the immediately preceding CALL.
Absent components clear their windows. Epochs, gaps, keys, and timestamps have
no authority to declare a row unchanged. Equality means identical canonical
typed row bytes. The frozen source ownership contract also permits reuse of a
previously validated geometry row while its exact object is retained.

The writer owns all encoded trees. The reader caches encoded rows and decodes
each complete call afresh, so mutable candle dictionaries are never shared with
later engine calls. Caches have explicit row and canonical-byte bounds.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from input_codec import encode


ENCODING = "tachyos.snapshot_delta.v1"
TAG = "$snapshot_delta"
SEQUENCE = "previous_window.v1"
MAX_SNAPSHOT_ROWS = 10_000
MAX_SNAPSHOT_BYTES = 32_000_000
COMPONENTS = ("geometry_rows", "historical_candles")


class SnapshotDeltaError(ValueError):
    """A compact snapshot cannot be expanded into an accepted complete input."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class _Row:
    value: object
    key: bytes


def _empty_windows():
    return {name: [] for name in COMPONENTS}


class SnapshotDeltaEncoder:
    """Single-writer state, bounded by the two immediately preceding windows."""

    def __init__(self):
        self._previous = _empty_windows()
        self._geometry_memo = {}
        self._sequence = 0
        self._counts = {"calls": 0, "geometry_encodes": 0,
                        "immutable_geometry_reuses": 0, "reused_rows": 0,
                        "literal_rows": 0}

    def stats(self):
        return {"enabled": True, "encoding": ENCODING, **self._counts,
                "max_snapshot_rows": MAX_SNAPSHOT_ROWS,
                "max_snapshot_bytes": MAX_SNAPSHOT_BYTES,
                **{name: {"rows": len(self._previous[name]),
                          "bytes": sum(len(row.key) for row in self._previous[name])}
                   for name in COMPONENTS}}

    def encode(self, pinned, sequence):
        if type(sequence) is not int or sequence != self._sequence + 1:
            raise SnapshotDeltaError("DELTA_CALL_SEQUENCE_INVALID")
        following = _empty_windows()
        memo = {}
        seen = set()
        increments = dict.fromkeys(self._counts, 0)

        def snapshot(name, kind, values, encode_row, immutable):
            if name not in COMPONENTS or name in seen or kind not in ("list", "tuple"):
                raise SnapshotDeltaError("DELTA_COMPONENT_INVALID")
            seen.add(name)
            if len(values) > MAX_SNAPSHOT_ROWS:
                raise SnapshotDeltaError("SNAPSHOT_ROW_LIMIT")
            previous = self._previous[name]
            by_value = {}
            for index, row in enumerate(previous):
                by_value.setdefault(row.key, index)
            current = following[name]
            pieces = []
            total = 0
            for value in values:
                cached = self._geometry_memo.get(id(value)) if immutable else None
                if cached is not None and cached[0] is value:
                    row = cached[1]
                    increments["immutable_geometry_reuses"] += 1
                else:
                    encoded = encode_row(value)
                    row = _Row(encoded, _canonical(encoded))
                    if immutable:
                        increments["geometry_encodes"] += 1
                total += len(row.key)
                if total > MAX_SNAPSHOT_BYTES:
                    raise SnapshotDeltaError("SNAPSHOT_BYTE_LIMIT")

                index = by_value.get(row.key)
                if index is not None:
                    # Prefer the next consecutive equal row to keep duplicate
                    # snapshots compact without changing their multiplicity.
                    if pieces and pieces[-1][0] == "copy":
                        next_index = pieces[-1][1] + pieces[-1][2]
                        if next_index < len(previous) and previous[next_index].key == row.key:
                            index = next_index
                    row = previous[index]
                    if pieces and pieces[-1][0] == "copy" and pieces[-1][1] + pieces[-1][2] == index:
                        pieces[-1][2] += 1
                    else:
                        pieces.append(["copy", index, 1])
                    increments["reused_rows"] += 1
                else:
                    if pieces and pieces[-1][0] == "literal":
                        pieces[-1][1].append(row.value)
                    else:
                        pieces.append(["literal", [row.value]])
                    increments["literal_rows"] += 1
                current.append(row)
                if immutable:
                    # Keep the actual object alive, not just its reusable id.
                    memo[id(value)] = (value, row)
            return {TAG: SEQUENCE, "kind": kind, "length": len(current), "pieces": pieces}

        envelope = encode(pinned, snapshot_encoder=snapshot)
        result = {"encoding": ENCODING, "base_sequence": self._sequence,
                  "envelope": envelope}
        self._previous = following
        self._geometry_memo = memo
        self._sequence = sequence
        increments["calls"] = 1
        for name, count in increments.items():
            self._counts[name] += count
        return result


def _member(node, key, *, fields=False):
    """Find a typed-tree pair without accepting malformed/duplicate members."""
    if type(node) is not dict:
        return None
    if fields:
        if node.get("$tachyos") != "dataclass" or node.get("name") != "FeedSnapshot":
            return None
        pairs = node.get("fields")
    else:
        if node.get("$tachyos") not in ("dict", "mappingproxy"):
            return None
        pairs = node.get("items")
    if type(pairs) is not list:
        return None
    found = None
    for pair in pairs:
        if type(pair) is list and len(pair) == 2 and pair[0] == key:
            if found is not None:
                raise SnapshotDeltaError("DELTA_DUPLICATE_MEMBER")
            found = pair
    return found


class SnapshotDeltaDecoder:
    """Expand private verified typed trees; do not expose cached mutable rows."""

    def __init__(self):
        self._previous = _empty_windows()
        self._sequence = 0

    def expand(self, payload, sequence):
        if (type(sequence) is not int or sequence != self._sequence + 1
                or type(payload) is not dict
                or set(payload) != {"encoding", "base_sequence", "envelope"}
                or payload["encoding"] != ENCODING
                or type(payload["base_sequence"]) is not int
                or payload["base_sequence"] != self._sequence):
            raise SnapshotDeltaError("DELTA_BASE_OR_PAYLOAD_INVALID")
        following = _empty_windows()
        envelope = payload["envelope"]
        call = _member(envelope, "call")
        method = _member(call[1], "method") if call is not None else None
        arguments = _member(call[1], "arguments") if call is not None else None
        if method is not None and method[1] == "process" and arguments is not None:
            feed = _member(arguments[1], "feed")
            targets = {
                "geometry_rows": _member(feed[1], "geometry_rows", fields=True) if feed is not None else None,
                "historical_candles": _member(arguments[1], "historical_candles"),
            }
            for name, pair in targets.items():
                if pair is not None and type(pair[1]) is dict and TAG in pair[1]:
                    node, rows = self._expand_sequence(pair[1], self._previous[name])
                    pair[1] = node
                    following[name] = rows
        self._previous = following
        self._sequence = sequence
        return envelope

    @staticmethod
    def _expand_sequence(node, previous):
        if (set(node) != {TAG, "kind", "length", "pieces"}
                or node[TAG] != SEQUENCE or node["kind"] not in ("list", "tuple")
                or type(node["length"]) is not int
                or not 0 <= node["length"] <= MAX_SNAPSHOT_ROWS
                or type(node["pieces"]) is not list
                or len(node["pieces"]) > node["length"]):
            raise SnapshotDeltaError("DELTA_SEQUENCE_INVALID")
        rows = []
        total = 0
        for piece in node["pieces"]:
            if type(piece) is not list or not piece:
                raise SnapshotDeltaError("DELTA_PIECE_INVALID")
            if piece[0] == "copy":
                if (len(piece) != 3 or type(piece[1]) is not int or type(piece[2]) is not int
                        or piece[1] < 0 or piece[2] <= 0
                        or piece[1] + piece[2] > len(previous)):
                    raise SnapshotDeltaError("DELTA_REFERENCE_OUT_OF_RANGE")
                count = piece[2]
                if len(rows) + count > node["length"]:
                    raise SnapshotDeltaError("DELTA_LENGTH_MISMATCH")
                for index in range(piece[1], piece[1] + count):
                    row = previous[index]
                    total += len(row.key)
                    if total > MAX_SNAPSHOT_BYTES:
                        raise SnapshotDeltaError("SNAPSHOT_BYTE_LIMIT")
                    rows.append(row)
            elif piece[0] == "literal":
                if len(piece) != 2 or type(piece[1]) is not list or not piece[1]:
                    raise SnapshotDeltaError("DELTA_LITERAL_INVALID")
                if len(rows) + len(piece[1]) > node["length"]:
                    raise SnapshotDeltaError("DELTA_LENGTH_MISMATCH")
                for value in piece[1]:
                    row = _Row(value, _canonical(value))
                    total += len(row.key)
                    if total > MAX_SNAPSHOT_BYTES:
                        raise SnapshotDeltaError("SNAPSHOT_BYTE_LIMIT")
                    rows.append(row)
            else:
                raise SnapshotDeltaError("DELTA_PIECE_UNKNOWN")
        if len(rows) != node["length"]:
            raise SnapshotDeltaError("DELTA_LENGTH_MISMATCH")
        return {"$tachyos": node["kind"], "items": [row.value for row in rows]}, rows
