<!-- File at: https://github.com/google/json_serializable.dart/issues/new -->
<!-- Title: -->
# `int` fields silently truncate fractional values and saturate out-of-range values when decoding from a `double` literal

Since 6.8.0 ("Handle decoding an `int` value from a `double` literal"), `int` fields are decoded as `(json['id'] as num).toInt()`. This correctly accepts `42.0` as `42`. But the same code also **silently accepts inputs that are not integers or don't fit in an `int`**, and changes their value with no exception:

| JSON input | Decoded `id` (native: VM/AOT) | Decoded `id` (web: dart2js) |
|---|---|---|
| `{"id": 42.0}` | `42` ✅ | `42` ✅ |
| `{"id": 1.9}` | `1` ⚠️ fractional part dropped | `1` ⚠️ |
| `{"id": -1.9}` | `-1` ⚠️ | `-1` ⚠️ |
| `{"id": 99999999999999999999999999}` | `9223372036854775807` ⚠️ clamped to int64 max | `1e+26` |
| `{"id": -99999999999999999999999999}` | `-9223372036854775808` ⚠️ clamped to int64 min | `-1e+26` |
| `{"id": 1e300}` | `9223372036854775807` ⚠️ | `1e+300` |

For comparison, a hand-written `json['id'] as int` throws on every ⚠️ row.

This matters because the resulting value is plausible but wrong, not an error. A malformed or hostile payload (`"id": 1.9`, or an ID beyond int64 from a backend using arbitrary-precision integers) becomes a different, valid-looking ID. For example, every oversized ID collapses to the same `9223372036854775807`. On native the app sees no exception, and the same payload decodes to a different value on web.

`freezed` is affected identically, since it uses the same generated `fromJson`. I'm filing here because this is where the code is generated.

## Reproduction

Versions: Dart SDK 3.13.2 (macOS arm64), `json_serializable` 6.14.1, `json_annotation` 4.12.0 (also `freezed` 4.0.1 / `freezed_annotation` 3.1.0 for the freezed column).

```dart
// lib/model.dart
import 'package:json_annotation/json_annotation.dart';
part 'model.g.dart';

@JsonSerializable()
class Item {
  final int id;
  Item({required this.id});
  factory Item.fromJson(Map<String, dynamic> json) => _$ItemFromJson(json);
}
```

Generated:

```dart
Item _$ItemFromJson(Map<String, dynamic> json) =>
    Item(id: (json['id'] as num).toInt());
```

```dart
// bin/main.dart
import 'dart:convert';
import 'package:repro/model.dart';

void main() {
  for (final input in ['{"id": 1.9}', '{"id": 99999999999999999999999999}']) {
    print(Item.fromJson(jsonDecode(input) as Map<String, dynamic>).id);
  }
}
// native output:
// 1
// 9223372036854775807
```

## Expected

I'd expect the 6.8.0 behaviour to accept a `double` only when it represents an integer exactly (e.g. `42.0`), and to throw otherwise, as `as int` does. Currently the rounding and clamping of `double.toInt()` leak into deserialization.

## Possible fix

Only convert a `double` when it is integral and finite. For example, generate a call to a small helper in `json_annotation`:

```dart
int $intFromJson(Object? value) {
  if (value is int) return value;
  if (value is double &&
      value == value.truncateToDouble() && // integral (also false for NaN/±inf)
      value >= -9223372036854775808.0 &&
      value < 9223372036854775808.0) {    // fits in int64, so toInt() won't clamp
    return value.toInt();
  }
  throw ArgumentError.value(value, 'value', 'Not an integer');
}
```

I tested this on the VM. It accepts `42`, `42.0` and `-0.0`, and it throws on `1.9`, `9223372036854775808` (2^63), `1e26` and `1e300`. It can't catch a literal that `jsonDecode` has already rounded onto an in-range double (e.g. `-9223372036854775809` parses as exactly -2^63), but that loss happens before the generated code runs. On web, integral JSON numbers are already `int`, so the helper doesn't change web behaviour.

If silently truncating is intended, it would help to document it on `JsonSerializable`/`JsonKey`, since it differs from what `as int` does.

## How this was found

This came up while differential-testing four Dart JSON deserialization approaches against each other (hand-written `dart:convert`, `json_serializable`, `freezed`, `built_value`). In a schema-aware fuzzing campaign, `json_serializable`/`freezed` were the only two that accepted out-of-range integers. Write-up and data: https://doi.org/10.5281/zenodo.22555795

I'm happy to send a PR if a fix along these lines is welcome.
