namespace TechSupport.Console.Models;

public sealed class Customer
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public string? Organization { get; init; }
    public string? PhoneNumber { get; init; }
    public string? Notes { get; set; }
    public DateTimeOffset LastSession { get; set; }
    public int SessionCount { get; set; }
}

public sealed class SavedConnection
{
    public required string Id { get; init; }
    public required string Label { get; init; }
    public required string Host { get; init; }
    public int Port { get; init; } = 7022;
    public string? CustomerId { get; init; }
    public DateTimeOffset? LastConnected { get; set; }
}
