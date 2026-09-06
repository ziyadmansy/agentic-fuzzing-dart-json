// The batch harness (docs/dart-oracle-design.md Section 9). Reads
// newline-delimited JSON requests from stdin, one per candidate input:
//   {"input_b64": "<base64 of the candidate's raw bytes>"}
// and writes one newline-delimited JSON result per line to stdout, flushed
// immediately so a driver can attribute a later process-level (Tier A)
// crash to the correct input even though the harness itself is a single
// long-lived process handling an entire campaign.
//
// Build for an experiment run with:
//   dart compile exe bin/dart_json_harness.dart -o build/dart_json_harness
// Sanity check, matching the original project's harness smoke test:
//   printf '{"input_b64":"%s"}\n' "$(printf '{"id":1,"amount":"1","name":null,"status":"active","tags":[],"child":null}' | base64)" | ./build/dart_json_harness

import 'dart:convert';
import 'dart:io';

import '../lib/oracle.dart';

void main() async {
  await for (final line
      in stdin.transform(utf8.decoder).transform(const LineSplitter())) {
    if (line.trim().isEmpty) continue;
    final result = _processLine(line);
    stdout.writeln(jsonEncode(result));
    await stdout.flush();
  }
}

Map<String, dynamic> _processLine(String line) {
  final Map<String, dynamic> request;
  try {
    request = jsonDecode(line) as Map<String, dynamic>;
  } catch (e) {
    return {
      'status': 'harness_error',
      'reason': 'invalid_request_line',
      'message': e.toString(),
    };
  }

  final List<int> bytes;
  try {
    bytes = base64Decode(request['input_b64'] as String);
  } catch (e) {
    return {
      'status': 'harness_error',
      'reason': 'invalid_base64',
      'message': e.toString(),
    };
  }

  final String text;
  try {
    text = utf8.decode(bytes, allowMalformed: false);
  } catch (e) {
    return {
      'status': 'structural_reject',
      'reason': 'invalid_utf8',
      'message': e.toString(),
    };
  }

  final Object? decoded;
  try {
    decoded = jsonDecode(text);
  } catch (e) {
    return {
      'status': 'structural_reject',
      'reason': 'invalid_json_syntax',
      'message': e.toString(),
    };
  }

  if (decoded is! Map<String, dynamic>) {
    // Syntactically valid JSON (matches the grammar's `json : value EOF ;`,
    // handoff Section 2.1) but not an object, so none of the four schema
    // paths can run -- distinct from `structural_reject`, which means the
    // bytes were not even valid JSON. RQ1 (docs/dart-oracle-design.md
    // Section 1) counts this as accepted, matching cJSON's own grammar,
    // which accepts any value type at the top level, not just objects.
    return {
      'status': 'structural_valid_non_object',
      'decoded_type': decoded.runtimeType.toString(),
    };
  }

  return {
    'status': 'schema_evaluated',
    ...runOracle(decoded).toJson(),
  };
}
