// Path A: hand-written parsing with no codegen, using `dart:convert` and
// explicit `as` casts / null checks the way a typical un-audited Flutter
// codebase does it. Deliberately naive where a real developer would be naive
// (see docs/dart-oracle-design.md Section 3) so the divergences this produces
// are representative, not artificially injected.

enum ManualStatus { active, inactive, unknown }

class ManualRecord {
  final int id;
  final String amount;
  final String? name;
  final ManualStatus status;
  final List<String> tags;
  final ManualRecord? child;

  ManualRecord({
    required this.id,
    required this.amount,
    required this.name,
    required this.status,
    required this.tags,
    required this.child,
  });

  static ManualRecord fromJson(Map<String, dynamic> json) {
    return ManualRecord(
      id: json['id'] as int,
      amount: json['amount'] as String,
      name: json['name'] as String?,
      // Idiomatic-but-naive: `Enum.values.byName` throws a raw ArgumentError
      // for any string not exactly matching an enum name, rather than a
      // documented decoding exception. This is intentional (Tier B).
      status: ManualStatus.values.byName(json['status'] as String),
      tags: (json['tags'] as List).map((e) => e as String).toList(),
      child: json['child'] == null
          ? null
          : ManualRecord.fromJson(json['child'] as Map<String, dynamic>),
    );
  }
}
