using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TechSupport.Console.Models;

namespace TechSupport.Console.ViewModels;

public partial class CustomersViewModel : ObservableObject
{
    private readonly MainViewModel _main;

    [ObservableProperty] private Customer? _selected;
    [ObservableProperty] private string _searchText = "";
    [ObservableProperty] private SavedConnection? _selectedConnection;

    public ObservableCollection<Customer> All => _main.Store.Customers;
    public ICollectionView FilteredView { get; }

    public CustomersViewModel(MainViewModel main)
    {
        _main = main;
        FilteredView = CollectionViewSource.GetDefaultView(All);
        FilteredView.Filter = obj =>
        {
            if (string.IsNullOrWhiteSpace(SearchText)) return true;
            if (obj is not Customer c) return false;
            var q = SearchText.Trim();
            return Contains(c.Name, q)
                || Contains(c.Organization, q)
                || Contains(c.PhoneNumber, q)
                || Contains(c.Email, q);
        };
        FilteredView.SortDescriptions.Add(new SortDescription(
            nameof(Customer.Name), ListSortDirection.Ascending));
    }

    private static bool Contains(string? s, string q) =>
        s is not null && s.Contains(q, StringComparison.OrdinalIgnoreCase);

    partial void OnSearchTextChanged(string value) => FilteredView.Refresh();

    [RelayCommand]
    private void New()
    {
        var c = new Customer { Name = "New customer" };
        All.Add(c);
        Selected = c;
        _main.Store.RequestSave();
    }

    [RelayCommand(CanExecute = nameof(HasSelection))]
    private void Delete()
    {
        if (Selected is null) return;
        All.Remove(Selected);
        Selected = null;
        _main.Store.RequestSave();
    }

    [RelayCommand(CanExecute = nameof(HasSelection))]
    private void AddConnection()
    {
        if (Selected is null) return;
        var conn = new SavedConnection
        {
            Label = "New machine",
            Host = "",
            CustomerId = Selected.Id,
        };
        Selected.Connections.Add(conn);
        SelectedConnection = conn;
        _main.Store.RequestSave();
    }

    [RelayCommand(CanExecute = nameof(HasConnectionSelected))]
    private void RemoveConnection()
    {
        if (Selected is null || SelectedConnection is null) return;
        Selected.Connections.Remove(SelectedConnection);
        SelectedConnection = null;
        _main.Store.RequestSave();
    }

    [RelayCommand(CanExecute = nameof(HasConnectionSelected))]
    private async Task ConnectAsync()
    {
        if (Selected is null || SelectedConnection is null) return;
        await _main.StartSessionAsync(
            SelectedConnection.Host, SelectedConnection.Port, Selected.Id)
            .ConfigureAwait(true);
    }

    private bool HasSelection() => Selected is not null;
    private bool HasConnectionSelected() => SelectedConnection is not null;

    partial void OnSelectedChanging(Customer? oldValue, Customer? newValue)
    {
        if (oldValue is not null) oldValue.PropertyChanged -= OnCustomerEdited;
        if (newValue is not null) newValue.PropertyChanged += OnCustomerEdited;
    }

    partial void OnSelectedChanged(Customer? value)
    {
        DeleteCommand.NotifyCanExecuteChanged();
        AddConnectionCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedConnectionChanging(SavedConnection? oldValue, SavedConnection? newValue)
    {
        if (oldValue is not null) oldValue.PropertyChanged -= OnConnectionEdited;
        if (newValue is not null) newValue.PropertyChanged += OnConnectionEdited;
    }

    partial void OnSelectedConnectionChanged(SavedConnection? value)
    {
        RemoveConnectionCommand.NotifyCanExecuteChanged();
        ConnectCommand.NotifyCanExecuteChanged();
    }

    private void OnCustomerEdited(object? sender, PropertyChangedEventArgs e) =>
        _main.Store.RequestSave();

    private void OnConnectionEdited(object? sender, PropertyChangedEventArgs e) =>
        _main.Store.RequestSave();
}
