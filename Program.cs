using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using TimelineZLA;
using TimelineZLA.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

builder.Services.AddScoped(sp => new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
builder.Services.AddScoped<PdfExportService>();
builder.Services.AddScoped<TimelineZLA.Services.TimelineStorageService>();
builder.Services.AddScoped<TimelineZLA.Services.SyncService>();

await builder.Build().RunAsync();

