// The schema-stage oracle (docs/dart-oracle-design.md Section 9, stage 2):
// runs all four paths against one already-`jsonDecode`d Map, classifies each
// path's outcome, and computes Tier B (private/undocumented exception type)
// and Tier C (cross-path divergence) purely from those four outcomes.

import 'canonical.dart';
import 'schema/built_value_model.dart';
import 'schema/freezed_model.dart';
import 'schema/json_serializable_model.dart';
import 'schema/manual.dart';
import 'schema/serializers.dart';

class PathResult {
  final String path;
  final bool accepted;
  final Map<String, dynamic>? canonical;
  final String? exceptionType;
  final bool? isPrivate;
  final String? message;

  PathResult.accepted(this.path, Map<String, dynamic> this.canonical)
      : accepted = true,
        exceptionType = null,
        isPrivate = null,
        message = null;

  PathResult.rejected(this.path, Object error)
      : accepted = false,
        canonical = null,
        // Dart's leading-underscore convention marks a class as private to
        // its defining library -- this operationalizes docs/dart-oracle-
        // design.md's "undocumented failure surface" finding (Section 8,
        // item 3) mechanically, not via a hand-maintained per-package list.
        exceptionType = error.runtimeType.toString(),
        isPrivate = error.runtimeType.toString().startsWith('_'),
        message = error.toString();

  Map<String, dynamic> toJson() => accepted
      ? {'path': path, 'status': 'accepted', 'canonical': canonical}
      : {
          'path': path,
          'status': 'rejected',
          'exception_type': exceptionType,
          'is_private': isPrivate,
          'message': message,
        };
}

PathResult _runPath(String name, Map<String, dynamic> Function() decode) {
  try {
    return PathResult.accepted(name, decode());
  } catch (e) {
    return PathResult.rejected(name, e);
  }
}

class OracleResult {
  final List<PathResult> paths;
  OracleResult(this.paths);

  List<String> get tierBPaths =>
      paths.where((p) => p.isPrivate == true).map((p) => p.path).toList();

  /// 'none' | 'accept_reject' | 'value'
  String get tierCDivergence {
    final acceptedFlags = paths.map((p) => p.accepted).toSet();
    if (acceptedFlags.length > 1) return 'accept_reject';
    if (acceptedFlags.single) {
      final first = paths.first.canonical;
      for (final p in paths.skip(1)) {
        if (!canonicalEquals(first, p.canonical)) return 'value';
      }
    }
    return 'none';
  }

  Map<String, dynamic> toJson() => {
        'paths': paths.map((p) => p.toJson()).toList(),
        'tier_b_paths': tierBPaths,
        'tier_c_divergence': tierCDivergence,
      };
}

OracleResult runOracle(Map<String, dynamic> json) {
  return OracleResult([
    _runPath('A_manual', () => canonicalManual(ManualRecord.fromJson(json))),
    _runPath('B_json_serializable',
        () => canonicalJs(JsRecord.fromJson(json))),
    _runPath('C_freezed',
        () => canonicalFreezed(FreezedRecord.fromJson(json))),
    _runPath(
        'D_built_value',
        () => canonicalBv(
            serializers.deserializeWith(BvRecord.serializer, json)!)),
  ]);
}
