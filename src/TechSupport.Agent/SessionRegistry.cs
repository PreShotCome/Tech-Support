using System.Collections.Concurrent;

namespace TechSupport.Agent;

public sealed class SessionRegistry
{
    private readonly ConcurrentDictionary<string, Session> _sessions = new();

    public bool TryAdd(Session session) => _sessions.TryAdd(session.Id, session);

    public bool TryRemove(string id, out Session? session)
    {
        var ok = _sessions.TryRemove(id, out var s);
        session = s;
        return ok;
    }

    public IReadOnlyCollection<Session> Active => _sessions.Values.ToArray();
}

public sealed record Session(
    string Id,
    string TechnicianId,
    string TechnicianName,
    DateTimeOffset StartedUtc,
    string RemoteAddress);
