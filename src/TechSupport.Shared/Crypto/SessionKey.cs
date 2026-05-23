using System.Security.Cryptography;
using System.Text;

namespace TechSupport.Shared.Crypto;

/// <summary>
/// Derives short, memorable session codes (e.g. WORD-WORD-NNN) used to
/// pair a technician with an unattended agent. The agent registers under
/// a deterministic pairing token; the technician types the code to find
/// the agent through the relay.
///
/// This is NOT the transport encryption key — TLS (or DTLS via the relay)
/// handles confidentiality on the wire. This is a discovery / pairing
/// secret only.
/// </summary>
public static class SessionKey
{
    private static readonly string[] Wordlist =
    {
        "amber", "anvil", "aspen", "atlas", "azure", "basil", "birch", "blaze",
        "brisk", "cedar", "clay", "cobalt", "coral", "crisp", "delta", "drift",
        "ember", "fable", "flint", "forge", "frost", "glade", "harbor", "heron",
        "ivory", "jade", "kite", "lark", "linen", "lumen", "maple", "meadow",
        "north", "oasis", "onyx", "opal", "pebble", "pine", "plume", "quartz",
        "raven", "river", "rune", "sable", "saffron", "spruce", "stone", "swift",
        "thistle", "tide", "topaz", "umber", "valley", "willow", "yarrow", "zephyr",
    };

    public static string Generate()
    {
        Span<byte> bytes = stackalloc byte[4];
        RandomNumberGenerator.Fill(bytes);
        var i1 = bytes[0] % Wordlist.Length;
        var i2 = bytes[1] % Wordlist.Length;
        var n = ((bytes[2] << 8) | bytes[3]) % 1000;
        return $"{Wordlist[i1]}-{Wordlist[i2]}-{n:000}";
    }

    public static string Fingerprint(string sessionCode)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(sessionCode));
        return Convert.ToHexString(hash.AsSpan(0, 8));
    }
}
