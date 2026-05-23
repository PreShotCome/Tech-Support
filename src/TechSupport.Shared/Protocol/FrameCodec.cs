using System.Buffers;
using System.Buffers.Binary;
using System.IO.Pipelines;

namespace TechSupport.Shared.Protocol;

/// <summary>
/// Length-prefixed framing over a duplex stream. Each frame is:
///   [u32 length] [u8 type] [payload]
/// Length covers the type byte plus payload.
/// </summary>
public static class FrameCodec
{
    public const int MaxFrameSize = 32 * 1024 * 1024;

    public static async ValueTask WriteAsync(
        Stream stream,
        MessageType type,
        ReadOnlyMemory<byte> payload,
        CancellationToken ct = default)
    {
        var header = new byte[5];
        BinaryPrimitives.WriteUInt32BigEndian(header, (uint)(payload.Length + 1));
        header[4] = (byte)type;
        await stream.WriteAsync(header, ct).ConfigureAwait(false);
        if (!payload.IsEmpty)
            await stream.WriteAsync(payload, ct).ConfigureAwait(false);
    }

    public static async ValueTask<(MessageType Type, byte[] Payload)> ReadAsync(
        PipeReader reader,
        CancellationToken ct = default)
    {
        while (true)
        {
            var result = await reader.ReadAsync(ct).ConfigureAwait(false);
            var buffer = result.Buffer;

            if (TryParse(ref buffer, out var type, out var payload))
            {
                reader.AdvanceTo(buffer.Start);
                return (type, payload);
            }

            reader.AdvanceTo(buffer.Start, buffer.End);

            if (result.IsCompleted)
                throw new EndOfStreamException("Stream closed mid-frame.");
        }
    }

    /// <summary>
    /// Raw-stream alternative to the PipeReader version. Reads exactly
    /// the bytes it needs from the stream so we don't depend on
    /// StreamPipeReader semantics, which can stall over loopback
    /// NetworkStreams in some Windows configurations.
    /// </summary>
    public static async ValueTask<(MessageType Type, byte[] Payload)> ReadFromStreamAsync(
        Stream stream,
        CancellationToken ct = default)
    {
        var header = new byte[5];
        await ReadExactAsync(stream, header, ct).ConfigureAwait(false);
        var length = BinaryPrimitives.ReadUInt32BigEndian(header);
        if (length == 0 || length > MaxFrameSize)
            throw new InvalidDataException($"Frame length {length} out of range.");
        var type = (MessageType)header[4];

        var payloadLength = (int)length - 1;
        var payload = new byte[payloadLength];
        if (payloadLength > 0)
            await ReadExactAsync(stream, payload, ct).ConfigureAwait(false);
        return (type, payload);
    }

    private static async ValueTask ReadExactAsync(Stream stream, Memory<byte> buffer, CancellationToken ct)
    {
        var remaining = buffer;
        while (!remaining.IsEmpty)
        {
            var n = await stream.ReadAsync(remaining, ct).ConfigureAwait(false);
            if (n == 0)
                throw new EndOfStreamException(
                    $"Stream closed with {remaining.Length} bytes still expected.");
            remaining = remaining.Slice(n);
        }
    }

    private static bool TryParse(
        ref ReadOnlySequence<byte> buffer,
        out MessageType type,
        out byte[] payload)
    {
        type = MessageType.Unknown;
        payload = Array.Empty<byte>();

        if (buffer.Length < 5) return false;

        Span<byte> header = stackalloc byte[5];
        buffer.Slice(0, 5).CopyTo(header);
        var length = BinaryPrimitives.ReadUInt32BigEndian(header);

        if (length == 0 || length > MaxFrameSize)
            throw new InvalidDataException($"Frame length {length} out of range.");

        if (buffer.Length < 5 + length) return false;

        type = (MessageType)header[4];
        var payloadLength = (int)length - 1;
        payload = new byte[payloadLength];
        buffer.Slice(5, payloadLength).CopyTo(payload);

        buffer = buffer.Slice(5 + length);
        return true;
    }
}
