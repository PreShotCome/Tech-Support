using System.Collections.ObjectModel;
using System.IO;
using System.Text.Json;
using TechSupport.Console.Models;

namespace TechSupport.Console.Services;

/// <summary>
/// JSON-backed store for customers. One file per install under
/// %APPDATA%/TechSupport. Save is debounced to avoid thrash when the
/// user is typing into a notes field.
/// </summary>
public sealed class CustomerStore
{
    private readonly string _path;
    private readonly JsonSerializerOptions _json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };
    private readonly SemaphoreSlim _saveGate = new(1, 1);
    private readonly object _writeLock = new();
    private CancellationTokenSource? _saveCts;

    public ObservableCollection<Customer> Customers { get; } = new();

    public CustomerStore() : this(DefaultPath()) { }

    public CustomerStore(string path)
    {
        _path = path;
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        Load();
    }

    private static string DefaultPath() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "TechSupport",
        "customers.json");

    private void Load()
    {
        if (!File.Exists(_path)) return;
        try
        {
            using var stream = File.OpenRead(_path);
            var snapshot = JsonSerializer.Deserialize<Snapshot>(stream, _json);
            if (snapshot?.Customers is null) return;
            foreach (var c in snapshot.Customers)
                Customers.Add(c);
        }
        catch (Exception ex) when (ex is JsonException or IOException)
        {
            BackupCorrupt();
        }
    }

    private void BackupCorrupt()
    {
        var backup = _path + $".broken.{DateTime.UtcNow:yyyyMMddHHmmss}";
        try { File.Move(_path, backup); } catch { /* best effort */ }
    }

    /// <summary>Schedules a save after a short debounce.</summary>
    public void RequestSave()
    {
        _saveCts?.Cancel();
        _saveCts = new CancellationTokenSource();
        var ct = _saveCts.Token;
        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay(TimeSpan.FromMilliseconds(400), ct).ConfigureAwait(false);
                await SaveAsync().ConfigureAwait(false);
            }
            catch (OperationCanceledException) { }
        });
    }

    public async Task SaveAsync()
    {
        await _saveGate.WaitAsync().ConfigureAwait(false);
        try
        {
            Snapshot snapshot;
            lock (_writeLock) snapshot = new Snapshot(Customers.ToList());

            var tmp = _path + ".tmp";
            await using (var stream = File.Create(tmp))
                await JsonSerializer.SerializeAsync(stream, snapshot, _json).ConfigureAwait(false);

            File.Move(tmp, _path, overwrite: true);
        }
        finally
        {
            _saveGate.Release();
        }
    }

    public Customer? FindByConnection(string host, int port) =>
        Customers.FirstOrDefault(c =>
            c.Connections.Any(x => x.Host == host && x.Port == port));

    private sealed record Snapshot(List<Customer> Customers);
}
