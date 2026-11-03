using System.Net.Http.Json;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace HollowdeepWiki.Data;

public sealed partial class WikiService(HttpClient http)
{
    static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true };
    Task? _loading;

    public Wiki Wiki { get; private set; } = new();
    public Release Release { get; private set; } = new();
    public bool Ready { get; private set; }

    public Task EnsureLoadedAsync() => _loading ??= LoadAsync();

    async Task LoadAsync()
    {
        var wiki = http.GetFromJsonAsync<Wiki>("data/wiki.json", Json);
        var release = http.GetFromJsonAsync<Release>("data/release.json", Json);
        Wiki = await wiki ?? new();
        Release = await release ?? new();
        foreach (var c in Wiki.Categories)
            foreach (var e in c.Entries)
            {
                e.Category = c;
                var body = string.Join(' ', e.Blocks.Select(b => b.Text ?? b.Html ?? ""));
                e.SearchText = $"{e.Name} {c.Title} {Tags().Replace(body, " ")}".ToLowerInvariant();
            }
        Ready = true;
    }

    public IEnumerable<Entry> AllEntries => Wiki.Categories.SelectMany(c => c.Entries);

    public Category? FindCategory(string slug) => Wiki.Categories.FirstOrDefault(c => c.Slug == slug);

    public IEnumerable<IGrouping<string, Category>> Groups => Wiki.Categories.GroupBy(c => c.Group);

    public List<Entry> Search(string query, int max = 30)
    {
        var words = query.ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (words.Length == 0) return new();
        return AllEntries
            .Where(e => words.All(e.SearchText.Contains))
            .OrderByDescending(e => words.Count(w => e.Name.Contains(w, StringComparison.OrdinalIgnoreCase)))
            .Take(max)
            .ToList();
    }

    [GeneratedRegex("<[^>]+>")]
    private static partial Regex Tags();
}
