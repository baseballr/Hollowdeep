using System.Text.Json.Serialization;

namespace HollowdeepWiki.Data;

public sealed class Wiki
{
    public string Version { get; set; } = "";
    public Stats Stats { get; set; } = new();
    public List<Category> Categories { get; set; } = new();
    public List<Recipe> Recipes { get; set; } = new();
}

public sealed class Stats
{
    public int Topics { get; set; }
    public int Mobs { get; set; }
    public int Items { get; set; }
    public int Recipes { get; set; }
}

public sealed class Category
{
    public string Slug { get; set; } = "";
    public string Title { get; set; } = "";
    public string Blurb { get; set; } = "";
    public string Group { get; set; } = "";
    public string? Icon { get; set; }
    public List<Entry> Entries { get; set; } = new();
}

public sealed class Entry
{
    public string Slug { get; set; } = "";
    public string Name { get; set; } = "";
    public string? Icon { get; set; }
    public string Summary { get; set; } = "";
    public List<Block> Blocks { get; set; } = new();

    [JsonIgnore] public Category Category { get; set; } = null!;
    [JsonIgnore] public string SearchText { get; set; } = "";
    public string Href => $"wiki/{Category.Slug}/{Slug}";
}

public sealed class Block
{
    public string T { get; set; } = "";
    public string? Text { get; set; }
    public string? Html { get; set; }
    public string? Title { get; set; }
    public string? Note { get; set; }
    public string? Icon { get; set; }
    public int Makes { get; set; } = 1;
    public List<List<Cell>>? Rows { get; set; }
}

public sealed class Cell
{
    public string Name { get; set; } = "";
    public string? Icon { get; set; }
}

public sealed class Recipe
{
    public string Name { get; set; } = "";
    public string Entry { get; set; } = "";
    public string Cat { get; set; } = "";
    public string Slug { get; set; } = "";
    public string? Icon { get; set; }
    public int Makes { get; set; } = 1;
    public List<List<Cell>> Rows { get; set; } = new();
    public string Href => $"wiki/{Cat}/{Slug}";
}

public sealed class Release
{
    public string Version { get; set; } = "";
    public string Tag { get; set; } = "";
    public string File { get; set; } = "";
    public string MinecraftMin { get; set; } = "";
    public string MinecraftMax { get; set; } = "";
    public string Notes { get; set; } = "";
    public string Download { get; set; } = "";
    public string ReleasePage { get; set; } = "";
    public string AllReleases { get; set; } = "";
    public long SizeBytes { get; set; }
    public string? Date { get; set; }

    public string Range => MinecraftMin == MinecraftMax ? MinecraftMin : $"{MinecraftMin} – {MinecraftMax}";
    public string Size => $"{SizeBytes / 1024.0 / 1024.0:0.0} MB";
}
