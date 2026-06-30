using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using PourAndMeasure;
using PourAndMeasure.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

builder.Services.AddScoped(sp => new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
builder.Services.AddScoped<PdfExportService>();
builder.Services.AddScoped<PourAndMeasure.Services.TimelineStorageService>();
builder.Services.AddScoped<PourAndMeasure.Services.SyncService>();

await builder.Build().RunAsync();
