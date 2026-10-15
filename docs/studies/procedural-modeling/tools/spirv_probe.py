"""Read word-count-prefixed SPIR-V modules in the selected Tiny Glade package.

Uses a caller-supplied Khronos core grammar as opcode metadata. This checks
instruction boundaries, not full SPIR-V semantics, target execution or GPU use.
No content digests are computed. All input/output paths are explicit.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct


def literal_string(words, start):
    raw = struct.pack("<" + "I" * (len(words) - start), *words[start:])
    end = raw.find(b"\0")
    if end < 0:
        raise ValueError("Unterminated SPIR-V string")
    return raw[:end].decode("utf-8"), (end + 4) // 4


def decode_module(blob, offset, count, grammar):
    words = struct.unpack_from("<" + "I" * count, blob, offset)
    if len(words) < 5 or words[0] != 0x07230203 or words[4] != 0:
        raise ValueError("Invalid module header")
    instructions, names, members, constants, definitions = [], {}, [], {}, {}
    position = 5
    while position < count:
        size, opcode = words[position] >> 16, words[position] & 65535
        if not size or position + size > count:
            raise ValueError(f"Invalid instruction boundary at word {position}")
        if opcode not in grammar:
            raise ValueError(f"Opcode {opcode} absent from supplied grammar")
        operands = list(words[position + 1:position + size])
        spec = grammar[opcode]
        row = {"word_offset": position, "file_offset": offset + position * 4,
               "opcode": opcode, "op": spec["opname"], "operands": operands}
        # Result IDs precede variable-width strings/arrays in the grammar.
        for index, operand in enumerate(spec.get("operands", [])):
            if operand["kind"] in ("IdResultType", "IdResult"):
                if index >= len(operands):
                    raise ValueError("Missing result operand")
                row["type_id" if operand["kind"] == "IdResultType" else "result_id"] = operands[index]
            if operand["kind"] == "LiteralString" or operand.get("quantifier"):
                break
        if opcode in (5, 7, 11):
            row["text"], _ = literal_string(operands, 1)
            names[str(operands[0])] = row["text"]
        elif opcode == 6:
            row["text"], _ = literal_string(operands, 2)
            members.append({"type_id": operands[0], "member": operands[1], "name": row["text"]})
        elif opcode == 15:
            row["text"], _ = literal_string(operands, 2)
        if "result_id" in row:
            definitions[row["result_id"]] = row
        instructions.append(row)
        position += size
    for row in instructions:
        if row["opcode"] == 43:
            type_row = definitions.get(row["type_id"])
            if type_row is None:
                raise ValueError("Constant without known type")
            payload = row["operands"][2:]
            if type_row["opcode"] == 22 and type_row["operands"][1] in (32, 64):
                width = type_row["operands"][1]
                value = struct.unpack("<f" if width == 32 else "<d", struct.pack("<" + "I" * len(payload), *payload))[0]
                if value == value and abs(value) != float("inf"):
                    constants[str(row["result_id"])] = {"type": "float" + str(width), "value": value}
            elif type_row["opcode"] == 21:
                width, signed = type_row["operands"][1:3]
                if width in (32, 64):
                    raw = struct.pack("<" + "I" * len(payload), *payload)
                    constants[str(row["result_id"])] = {"type": ("int" if signed else "uint") + str(width), "value": int.from_bytes(raw, "little", signed=bool(signed))}
    if not any(r["opcode"] == 14 for r in instructions) or not any(r["opcode"] == 15 for r in instructions):
        raise ValueError("No memory model or entry point")
    return {"offset": offset, "word_count": count, "version_word": hex(words[1]),
            "bound": words[3], "instruction_count": len(instructions),
            "opcode_counts": dict(Counter(r["op"] for r in instructions)),
            "entry_points": [r for r in instructions if r["opcode"] == 15],
            "execution_modes": [r for r in instructions if r["opcode"] in (16, 331)],
            "names": names, "member_names": members, "constants": constants,
            "instructions": instructions, "structure_complete": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--grammar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    grammar_data = json.loads(args.grammar.read_text(encoding="utf-8"))
    grammar = {r["opcode"]: r for r in grammar_data["instructions"]}
    blob = args.input.read_bytes()
    modules, candidates, rejected = [], 0, []
    position = 0
    while True:
        offset = blob.find(b"\x03\x02\x23\x07", position)
        if offset < 0:
            break
        candidates += 1
        position = offset + 4
        try:
            if offset < 4:
                raise ValueError("No preceding word count")
            count = struct.unpack_from("<I", blob, offset - 4)[0]
            if count < 5 or offset + count * 4 > len(blob):
                raise ValueError("Declared module outside selected file")
            module = decode_module(blob, offset, count, grammar)
            modules.append(module)
            position = offset + count * 4
        except (ValueError, struct.error, UnicodeDecodeError) as error:
            rejected.append({"offset": offset, "error": str(error)})
    if not modules:
        raise ValueError("No supported SPIR-V module")
    result = {"input": str(args.input.resolve()), "bytes": len(blob),
              "grammar": str(args.grammar.resolve()), "grammar_revision": grammar_data["revision"],
              "candidates": candidates, "rejected": rejected, "modules": modules,
              "limitations": ["Container bytes outside modules not decoded", "Not spirv-val semantic validation", "No runtime binding or GPU execution observed"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    text_path = args.output.with_suffix(".txt")
    lines = []
    for index, module in enumerate(modules):
        lines.append(f"MODULE {index} offset={module['offset']} words={module['word_count']}")
        for row in module["instructions"]:
            annotation = row.get("text", "")
            if "result_id" in row and str(row["result_id"]) in module["constants"]:
                annotation = str(module["constants"][str(row["result_id"])])
            lines.append(f"{row['word_offset']:06d} @{row['file_offset']:08x} {row['op']} {row['operands']} {annotation}")
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"modules": len(modules), "rejected": rejected, "instructions": sum(m["instruction_count"] for m in modules), "output": str(args.output)}))


if __name__ == "__main__":
    main()
