using CommunityToolkit.Mvvm.ComponentModel;
using TechSupport.Console.Models;

namespace TechSupport.Console.ViewModels;

public partial class HistoryViewModel : ObservableObject
{
    private readonly MainViewModel _main;

    public HistoryViewModel(MainViewModel main) => _main = main;

    public IEnumerable<HistoryRow> AllRows =>
        _main.Store.Customers.SelectMany(c =>
            c.History.Select(r => new HistoryRow(c, r)))
        .OrderByDescending(r => r.Record.StartedUtc);
}

public sealed record HistoryRow(Customer Customer, SessionRecord Record);
