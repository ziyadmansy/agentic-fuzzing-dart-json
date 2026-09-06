// Canonical-value comparator (docs/dart-oracle-design.md Section 4.1): each
// path's own typed result is converted into one shared Map/List/primitive
// shape so that a value divergence can never be a false positive introduced
// by the comparison logic itself -- comparison is on plain Dart primitives
// (String/int/bool/null/Map/List), never `double`, never a package-specific
// class's own `==`.

import 'schema/manual.dart';
import 'schema/json_serializable_model.dart';
import 'schema/freezed_model.dart';
import 'schema/built_value_model.dart';

Map<String, dynamic> canonicalManual(ManualRecord r) => {
      'id': r.id,
      'amount': r.amount,
      'name': r.name,
      'status': r.status.name,
      'tags': List<String>.from(r.tags),
      'child': r.child == null ? null : canonicalManual(r.child!),
    };

Map<String, dynamic> canonicalJs(JsRecord r) => {
      'id': r.id,
      'amount': r.amount,
      'name': r.name,
      'status': r.status.name,
      'tags': List<String>.from(r.tags),
      'child': r.child == null ? null : canonicalJs(r.child!),
    };

Map<String, dynamic> canonicalFreezed(FreezedRecord r) => {
      'id': r.id,
      'amount': r.amount,
      'name': r.name,
      'status': r.status.name,
      'tags': List<String>.from(r.tags),
      'child': r.child == null ? null : canonicalFreezed(r.child!),
    };

Map<String, dynamic> canonicalBv(BvRecord r) => {
      'id': r.id,
      'amount': r.amount,
      'name': r.name,
      'status': r.status.name,
      'tags': r.tags.toList(),
      'child': r.child == null ? null : canonicalBv(r.child!),
    };

/// Deep, order-sensitive structural equality over plain Map/List/primitive
/// trees. Deliberately hand-written rather than a package dependency: the
/// comparison is the one place a bug would silently invalidate every Tier C
/// result, so it stays small and auditable.
bool canonicalEquals(Object? a, Object? b) {
  if (a is Map && b is Map) {
    if (a.length != b.length) return false;
    for (final key in a.keys) {
      if (!b.containsKey(key)) return false;
      if (!canonicalEquals(a[key], b[key])) return false;
    }
    return true;
  }
  if (a is List && b is List) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (!canonicalEquals(a[i], b[i])) return false;
    }
    return true;
  }
  return a == b;
}
