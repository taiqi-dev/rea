// Offline PE metadata/CIL reader. The target assembly is never loaded or run.
// Uses only the installed .NET SDK libraries; computes no content digests.
using System.Globalization;
using System.Reflection.Emit;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text.Json;

if (args.Length is < 4 or > 5)
{
    Console.Error.WriteLine("usage: ManagedCilProbe assembly exact-type-or-* method-substring-or-* NEW-output.json [resolved-operand-substring]");
    return 2;
}
try
{
    var input = Path.GetFullPath(args[0]);
    using var file = File.OpenRead(input);
    using var pe = new PEReader(file);
    var metadata = pe.GetMetadataReader();
    var opcodes = typeof(OpCodes).GetFields().Where(f => f.FieldType == typeof(OpCode))
        .Select(f => (OpCode)f.GetValue(null)!)
        .ToDictionary(op => (int)unchecked((ushort)op.Value));

    string TypeName(TypeDefinitionHandle handle)
    {
        var type = metadata.GetTypeDefinition(handle);
        var parent = type.GetDeclaringType();
        var name = metadata.GetString(type.Name);
        if (!parent.IsNil) return TypeName(parent) + "+" + name;
        var ns = metadata.GetString(type.Namespace);
        return ns.Length == 0 ? name : ns + "." + name;
    }
    string Resolve(int token)
    {
        var handle = MetadataTokens.Handle(token);
        switch (handle.Kind)
        {
            case HandleKind.UserString:
                return JsonSerializer.Serialize(metadata.GetUserString((UserStringHandle)handle));
            case HandleKind.TypeDefinition:
                return TypeName((TypeDefinitionHandle)handle);
            case HandleKind.TypeReference:
                var tr = metadata.GetTypeReference((TypeReferenceHandle)handle);
                return metadata.GetString(tr.Namespace) + "." + metadata.GetString(tr.Name);
            case HandleKind.MethodDefinition:
                var md = metadata.GetMethodDefinition((MethodDefinitionHandle)handle);
                return TypeName(md.GetDeclaringType()) + "::" + metadata.GetString(md.Name);
            case HandleKind.FieldDefinition:
                var fd = metadata.GetFieldDefinition((FieldDefinitionHandle)handle);
                return TypeName(fd.GetDeclaringType()) + "::" + metadata.GetString(fd.Name);
            case HandleKind.MemberReference:
                var mr = metadata.GetMemberReference((MemberReferenceHandle)handle);
                return Resolve(MetadataTokens.GetToken(mr.Parent)) + "::" + metadata.GetString(mr.Name);
            case HandleKind.MethodSpecification:
                return Resolve(MetadataTokens.GetToken(metadata.GetMethodSpecification((MethodSpecificationHandle)handle).Method));
            default:
                return $"{handle.Kind}:0x{token:X8}";
        }
    }

    var selected = metadata.TypeDefinitions.Where(h => args[1] == "*" || TypeName(h) == args[1]).ToArray();
    if (selected.Length == 0 || (args[1] != "*" && selected.Length != 1))
        throw new InvalidDataException("Expected exactly one exact type match or a nonempty wildcard selection");
    var examinedMethods = 0;
    var decodedMethods = 0;
    var rows = new List<object>();
    foreach (var type in selected)
    foreach (var handle in metadata.GetTypeDefinition(type).GetMethods())
    {
        var method = metadata.GetMethodDefinition(handle);
        var name = metadata.GetString(method.Name);
        if (args[2] != "*" && !name.Contains(args[2], StringComparison.Ordinal)) continue;
        examinedMethods++;
        if (method.RelativeVirtualAddress == 0)
        {
            if (args.Length == 4)
                rows.Add(new { token = $"0x{MetadataTokens.GetToken(handle):X8}", type = TypeName(type), name, status = "no-body" });
            continue;
        }
        var body = pe.GetMethodBody(method.RelativeVirtualAddress);
        var il = body.GetILBytes() ?? [];
        var position = 0;
        ReadOnlySpan<byte> Take(int length)
        {
            if (length < 0 || length > il.Length - position)
                throw new InvalidDataException("CIL operand exceeds method body");
            var result = il.AsSpan(position, length);
            position += length;
            return result;
        }
        decodedMethods++;
        var instructions = new List<object>();
        var matchedOperand = args.Length == 4;
        while (position < il.Length)
        {
            var at = position;
            var code = (int)Take(1)[0];
            if (code == 0xFE) code = 0xFE00 | Take(1)[0];
            if (!opcodes.TryGetValue(code, out var op)) throw new InvalidDataException($"Unknown CIL opcode {code:X}");
            object? value = null;
            string? resolved = null;
            switch (op.OperandType)
            {
                case OperandType.InlineNone: break;
                case OperandType.ShortInlineI: value = unchecked((sbyte)Take(1)[0]); break;
                case OperandType.ShortInlineVar: value = Take(1)[0]; break;
                case OperandType.InlineVar: value = BitConverter.ToUInt16(Take(2)); break;
                case OperandType.InlineI: value = BitConverter.ToInt32(Take(4)); break;
                case OperandType.InlineI8: value = BitConverter.ToInt64(Take(8)); break;
                case OperandType.ShortInlineR: value = BitConverter.ToSingle(Take(4)).ToString("R", CultureInfo.InvariantCulture); break;
                case OperandType.InlineR: value = BitConverter.ToDouble(Take(8)).ToString("R", CultureInfo.InvariantCulture); break;
                case OperandType.ShortInlineBrTarget:
                    var shortDelta = unchecked((sbyte)Take(1)[0]); value = position + shortDelta; break;
                case OperandType.InlineBrTarget:
                    var delta = BitConverter.ToInt32(Take(4)); value = position + delta; break;
                case OperandType.InlineSwitch:
                    var count = BitConverter.ToInt32(Take(4));
                    if (count < 0 || count > (il.Length - position) / 4) throw new InvalidDataException("Invalid CIL switch table");
                    var end = position + count * 4;
                    var targets = new int[count];
                    for (var i = 0; i < count; i++) targets[i] = end + BitConverter.ToInt32(Take(4));
                    value = targets; break;
                case OperandType.InlineString:
                case OperandType.InlineSig:
                case OperandType.InlineMethod:
                case OperandType.InlineField:
                case OperandType.InlineType:
                case OperandType.InlineTok:
                    var token = BitConverter.ToInt32(Take(4)); value = $"0x{token:X8}"; resolved = Resolve(token); break;
                default: throw new InvalidDataException($"Unsupported CIL operand type {op.OperandType}");
            }
            if (args.Length == 5 && resolved?.Contains(args[4], StringComparison.Ordinal) == true)
                matchedOperand = true;
            instructions.Add(new { offset = at, opcode = op.Name, operand = value, resolved });
        }
        if (!matchedOperand) continue;
        rows.Add(new { token = $"0x{MetadataTokens.GetToken(handle):X8}", type = TypeName(type), name,
            rva = method.RelativeVirtualAddress, il_bytes = il.Length,
            signature = Convert.ToHexString(metadata.GetBlobBytes(method.Signature)),
            parameters = method.GetParameters().Select(h => metadata.GetParameter(h))
                .Select(p => new { sequence = p.SequenceNumber, name = metadata.GetString(p.Name) }),
            status = "decoded", instructions,
            exception_regions = body.ExceptionRegions.Select(r => new { kind = r.Kind.ToString(),
                r.TryOffset, r.TryLength, r.HandlerOffset, r.HandlerLength, r.FilterOffset }) });
    }
    var declaredFields = args[1] == "*" ? [] : selected.SelectMany(type =>
        metadata.GetTypeDefinition(type).GetFields().Select(handle =>
        {
            var field = metadata.GetFieldDefinition(handle);
            var constantHandle = field.GetDefaultValue();
            var constant = constantHandle.IsNil ? (Constant?)null : metadata.GetConstant(constantHandle);
            return new { token = $"0x{MetadataTokens.GetToken(handle):X8}", name = metadata.GetString(field.Name),
                flags = (int)field.Attributes,
                signature = Convert.ToHexString(metadata.GetBlobBytes(field.Signature)),
                field_type = field.DecodeSignature(new MetadataTypeNames(), metadata),
                custom_attributes = field.GetCustomAttributes().Select(h => metadata.GetCustomAttribute(h))
                    .Select(a => new { constructor = Resolve(MetadataTokens.GetToken(a.Constructor)),
                        value_bytes = Convert.ToHexString(metadata.GetBlobBytes(a.Value)) }).ToArray(),
                constant_type = constant?.TypeCode.ToString(),
                constant_bytes = constant is null ? null : Convert.ToHexString(metadata.GetBlobBytes(constant.Value.Value)) };
        })).ToArray();
    if (examinedMethods == 0 && !(args[2] == "*" && declaredFields.Length > 0))
        throw new InvalidDataException("No selected methods or declared fields");
    var result = new { input, bytes = file.Length,
        mvid = metadata.GetGuid(metadata.GetModuleDefinition().Mvid), type = args[1],
        coverage = new { selected_types = selected.Length, examined_methods = examinedMethods,
            decoded_methods = decodedMethods, operand_filter = args.Length == 5 ? args[4] : null },
        declared_fields = declaredFields,
        methods = rows, scope = "offline CIL/metadata only; no target execution or dependency loading" };
    var output = Path.GetFullPath(args[3]);
    Directory.CreateDirectory(Path.GetDirectoryName(output)!);
    using var destination = new FileStream(output, FileMode.CreateNew, FileAccess.Write);
    JsonSerializer.Serialize(destination, result, new JsonSerializerOptions { WriteIndented = true });
    Console.WriteLine(JsonSerializer.Serialize(new { methods = rows.Count, output }));
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.ToString());
    return 1;
}

// Decode names from metadata signatures without loading the target or resolving
// any dependency assembly. A name preserves shape; it is not a runtime type.
sealed class MetadataTypeNames : ISignatureTypeProvider<string, MetadataReader>
{
    public string GetArrayType(string elementType, ArrayShape shape) => elementType + "[" + new string(',', shape.Rank - 1) + "]";
    public string GetByReferenceType(string elementType) => elementType + "&";
    public string GetFunctionPointerType(MethodSignature<string> signature) => "methodptr(" + string.Join(",", signature.ParameterTypes) + ")->" + signature.ReturnType;
    public string GetGenericInstantiation(string genericType, System.Collections.Immutable.ImmutableArray<string> typeArguments) => genericType + "<" + string.Join(",", typeArguments) + ">";
    public string GetGenericMethodParameter(MetadataReader context, int index) => "!!" + index;
    public string GetGenericTypeParameter(MetadataReader context, int index) => "!" + index;
    public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired) => unmodifiedType + (isRequired ? " modreq(" : " modopt(") + modifier + ")";
    public string GetPinnedType(string elementType) => elementType + " pinned";
    public string GetPointerType(string elementType) => elementType + "*";
    public string GetPrimitiveType(PrimitiveTypeCode typeCode) => typeCode.ToString();
    public string GetSZArrayType(string elementType) => elementType + "[]";
    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte rawTypeKind)
    {
        var type = reader.GetTypeDefinition(handle);
        var name = reader.GetString(type.Name);
        var parent = type.GetDeclaringType();
        if (!parent.IsNil) return GetTypeFromDefinition(reader, parent, rawTypeKind) + "+" + name;
        var ns = reader.GetString(type.Namespace);
        return ns.Length == 0 ? name : ns + "." + name;
    }
    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte rawTypeKind)
    {
        var type = reader.GetTypeReference(handle);
        var name = reader.GetString(type.Name);
        if (type.ResolutionScope.Kind == HandleKind.TypeReference)
            return GetTypeFromReference(reader, (TypeReferenceHandle)type.ResolutionScope, rawTypeKind) + "+" + name;
        var ns = reader.GetString(type.Namespace);
        return ns.Length == 0 ? name : ns + "." + name;
    }
    public string GetTypeFromSpecification(MetadataReader reader, MetadataReader context, TypeSpecificationHandle handle, byte rawTypeKind)
        => reader.GetTypeSpecification(handle).DecodeSignature(this, context);
}
