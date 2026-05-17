# What's new in .NET 11

.NET 11 is the next annual release of the platform, currently in preview and scheduled to ship in November 2026. As a Standard Term Support (STS) release it succeeds the LTS .NET 10, and most of its surface area is already stable enough to try out in real projects.

This lesson is a tour of what is actually changing — the language additions, the runtime and JIT work, the ASP.NET Core updates, the BCL APIs you will reach for in day-to-day code, and the things you need to know before you bump a `<TargetFramework>` from `net10.0` to `net11.0`. It assumes you are comfortable with C# and have written or maintained a .NET app before.

## Where to get it and how to target it

Install the [.NET 11 preview SDK](https://dotnet.microsoft.com/download/dotnet/11.0), then change your project's target framework:

```xml
<PropertyGroup>
  <TargetFramework>net11.0</TargetFramework>
  <LangVersion>preview</LangVersion>
</PropertyGroup>
```

`<LangVersion>preview</LangVersion>` opts you into C# 15 features. You no longer need `<EnablePreviewFeatures>true</EnablePreviewFeatures>` for runtime-async on `net11.0` — that one was relaxed for this release. Other preview features (such as the discriminated-union scaffolding types) still require it.

## C# 15 language features

C# 15 ships with .NET 11. The headline additions are small but expressive.

### Union types

C# finally gets first-class *unions* — a value that can be one of several known case types, declared with the new `union` keyword:

```csharp
public record class Cat(string Name);
public record class Dog(string Name);
public record class Bird(string Name);

public union Pet(Cat, Dog, Bird);
```

The compiler provides implicit conversions from each case type into the union and makes `switch` exhaustiveness a hard guarantee. If you forget a case, the compiler tells you:

```csharp
Pet pet = new Dog("Rex");

string name = pet switch
{
    Dog d  => d.Name,
    Cat c  => c.Name,
    Bird b => b.Name,
};
```

If you removed the `Bird` arm, the switch expression would emit a non-exhaustive-pattern warning at compile time rather than risking an `InvalidOperationException` at runtime. The runtime side is exposed in `System.Runtime.CompilerServices` as `UnionAttribute` and `IUnion`, so libraries can author against the surface today; some features from the proposal (notably *union member providers*) are still being filled in across previews.

This is the feature people coming from F#, Rust, Swift, or TypeScript have been asking about for years. It replaces a pile of `OneOf<>`-style NuGet packages and ad-hoc inheritance hierarchies with one supported pattern.

### Collection expression arguments

Collection expressions in C# 12 gave you `[1, 2, 3]` and spreads. C# 15 lets you pass arguments to the underlying collection's constructor via a `with(...)` element at the head of the expression:

```csharp
string[] values = ["one", "two", "three"];

// Preallocate the List<T> capacity
List<string> names = [with(capacity: values.Length * 2), .. values];

// Pass a comparer to a HashSet<T>
HashSet<string> set = [with(StringComparer.OrdinalIgnoreCase),
                       "Hello", "HELLO", "hello"];
// set contains a single element.
```

Before C# 15, you had to fall back to `new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ... }` to thread a comparer through, which is awkward inside expressions or `init` initializers. `with(...)` keeps the collection expression syntax for the common cases that previously fell off the cliff.

## Runtime: the big change is Runtime Async

The biggest engineering investment in .NET 11 is finishing the move from compiler-generated async state machines to *runtime-native async*, called Runtime Async (or Runtime Async V2). Instead of the C# compiler emitting a state-machine class per `async` method, the runtime itself tracks suspension and resumption.

Opt in per project:

```xml
<PropertyGroup>
  <Features>runtime-async=on</Features>
</PropertyGroup>
```

The .NET 11 runtime libraries themselves are already compiled with `runtime-async=on`, so even apps that don't enable it pick up the change indirectly when they call into the BCL. ASP.NET Core's shared-framework libraries are also compiled with it on `net11.0+`.

### What you get

**Cleaner live stack traces.** This is the most visible effect. Walk a chain of three `await`s today and a `new StackTrace()` shows you ~13 frames threaded through `AsyncMethodBuilderCore.Start[TStateMachine]`. With Runtime Async you see the five frames that actually exist in your code:

```
   at Program.InnerAsync() in Program.cs:line 24
   at Program.MiddleAsync() in Program.cs:line 14
   at Program.OuterAsync() in Program.cs:line 8
   at Program.<Main>$(String[] args) in Program.cs:line 3
   at Program.<Main>(String[] args)
```

Profilers, debugger call-stack windows, and logging that captures live stacks all benefit. (Exception stack traces already looked clean because `ExceptionDispatchInfo` had been papering over the compiler-generated frames.)

**Lower overhead.** The runtime reuses continuation objects more aggressively and skips saving locals that didn't change across an await, so allocation pressure in async-heavy code drops.

**Better debugging.** Breakpoints inside runtime-async methods bind correctly, and stepping through `await` doesn't bounce you into compiler-generated infrastructure.

**Broader codegen.** Runtime Async now works under NativeAOT and ReadyToRun, including inlining of await-less async calls (the synchronous fast path).

### What to know

To opt *out* per project, use `<UseRuntimeAsync>false</UseRuntimeAsync>` in your `csproj`. The older `DOTNET_RuntimeAsync` and `UNSUPPORTED_RuntimeAsync` environment variables have been removed. Because Runtime Async changes codegen for a large portion of the framework, test your apps against the preview and watch for regressions around `ExecutionContext`/`AsyncLocal` flow and exception propagation.

## JIT and codegen improvements

The JIT picks up several optimizations that mostly show up after inlining, where guards from different methods land in the same compiled body.

**Constant-folding `SequenceEqual` and `string.Equals`.** When both operands are compile-time constants — string literals, `const string` fields, or UTF-8 literals like `"PNG"u8` — the JIT replaces the comparison with the constant result:

```csharp
static bool IsAdmin(string role) => role == "Admin";
// At a caller: IsAdmin("Guest") folds to false at JIT time after inlining.
```

**Better bounds-check elimination.** The pattern `i + cns < len` now elides the bounds check on the indexed access. Index-from-end (`values[^1]`) has more redundant checks removed. And the JIT now picks up the implicit `length != 0` assertion from a `span.IsEmpty` guard:

```csharp
if (!span.IsEmpty && span[0] == value)
{
    // span[0]'s bounds check is now elided.
}
```

**Redundant branch elimination.** If an outer predicate is already implied by an inner branch, or if you assign a value conditionally and immediately test it, the JIT now removes the redundant work:

```csharp
if (x > 0)
{
    if (x > 1) S();   // outer x > 0 is folded away
}

int y = condition ? 1 : 2;
if (y == 1) A(); else B(); // the test is eliminated — each ternary branch jumps directly
```

**Switch expression folding.** Patterns like `x is 0 or 1 or 2 or 3 or 4` collapse into branchless checks instead of a chain of comparisons.

**Hardware intrinsics.** New Arm SVE2 intrinsics land (`ShiftRightLogicalNarrowingSaturate(Even|Odd)`), `Half`↔`float` conversions on x64 with F16C use dedicated `vcvtph2ps` / `vcvtps2ph` instructions, and `Vector128.Dot` on AVX lowers to `mul + permute + add` instead of `vdpps`, which is consistently faster. The runtime also reports `SVE_AES`, `SVE_SHA3`, `SVE_SM4`, `SHA3`, and `SM4` as separate instruction sets.

**ReadyToRun.** Default comparers (`Comparer<T>.Default`, `EqualityComparer<T>.Default`) are now specialised in R2R images, mirroring NativeAOT — Microsoft's benchmarks show up to 20× improvement for collection operations that hit the default comparer. R2R can also devirtualise non-shared generic virtual calls.

**Cached interface dispatch on non-JIT platforms** — primarily iOS — yields up to 200× improvements in interface-heavy code, because what used to fall back to an expensive generic fixup path now uses the cached path.

**`Guid.NewGuid()` on Linux** now uses `getrandom()` with batch caching instead of reading from `/dev/urandom`, ≈12% faster.

## ASP.NET Core

### Kestrel and the request pipeline

Kestrel's HTTP/1.1 parser now uses a non-throwing code path for malformed requests, returning a result struct instead of throwing `BadHttpRequestException` on every parse failure. In hostile traffic (port scanning, misconfigured clients), throughput improves 20–40%; valid request processing is unaffected.

Kestrel also starts processing HTTP/3 requests without waiting for the control stream and SETTINGS frame, reducing first-request latency on new connections.

Two TLS observability changes make handshake failures debuggable. `ITlsHandshakeFeature.Exception` exposes the underlying exception from a failed handshake instead of surfacing a bare `IOException` higher up. The old `TlsClientHelloBytesCallback` option is now obsolete; configure ClientHello inspection via the new `ListenOptions.UseTlsClientHelloListener` connection middleware:

```csharp
builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenAnyIP(5001, listenOptions =>
    {
        listenOptions.Use(next => async context =>
        {
            await next(context);
            var tls = context.Features.Get<ITlsHandshakeFeature>();
            if (tls?.Exception is { } ex)
                Console.WriteLine($"TLS failed on {context.ConnectionId}: {ex.Message}");
        });

        listenOptions.UseTlsClientHelloListener((connection, helloBytes) =>
            Console.WriteLine($"ClientHello: {helloBytes.Length} bytes"));
        listenOptions.UseHttps();
    });
});
```

### Zstandard compression — on by default

ASP.NET Core picks up Zstandard for both response compression and request decompression, and `zstd` is enabled by default alongside Brotli and gzip. Browsers that advertise `Accept-Encoding: zstd` will now get Zstandard-compressed responses out of the box:

```csharp
builder.Services.AddResponseCompression();
builder.Services.AddRequestDecompression();
builder.Services.Configure<ZstandardCompressionProviderOptions>(options =>
{
    options.CompressionOptions = new ZstandardCompressionOptions { Quality = 6 };
});
```

The response-compression middleware now also adds `Vary: Accept-Encoding` to every response when compression is enabled, even if the response itself isn't compressed — important for CDNs and shared caches that key on encoding.

### Native OpenTelemetry tracing

ASP.NET Core now emits OpenTelemetry semantic-convention attributes on the HTTP server activity directly — no separate `OpenTelemetry.Instrumentation.AspNetCore` package required. Just subscribe to the `Microsoft.AspNetCore` activity source:

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .AddSource("Microsoft.AspNetCore")
        .AddConsoleExporter());
```

Attributes like `http.request.method`, `url.path`, `http.response.status_code`, and `server.address` are populated automatically. If you don't want them, flip the `Microsoft.AspNetCore.Hosting.SuppressActivityOpenTelemetryData` AppContext switch.

### Minimal APIs and OpenAPI

Endpoint filters now run even when parameter binding fails. The filter can inspect `HttpContext.Response.StatusCode == 400` and substitute its own response. In `Development`, set `RouteHandlerOptions.ThrowOnBadRequest = false` so the framework returns a 400 the filter can observe instead of throwing into the developer exception page.

`Microsoft.AspNetCore.OpenApi` updates to OpenAPI 3.2.0 via `Microsoft.OpenApi` 3.3.1 — a **breaking change** in the underlying library. Opt in to the new version explicitly:

```csharp
builder.Services.AddOpenApi(options =>
{
    options.OpenApiVersion = OpenApiSpecVersion.OpenApi3_2;
});
```

OpenAPI doc generation now recognises HTTP `QUERY` as a known operation type and emits `FileStreamResult` / `FileContentResult` types as binary string schemas instead of generic objects.

### Blazor

Blazor gets a long list of improvements; the ones most likely to affect existing apps:

**Virtualization no longer assumes equal item heights.** `Virtualize<TItem>` now adapts to measured item sizes at runtime, fixing scrolling glitches in mixed-height lists. The default `OverscanCount` rises from 3 to 15 to feed the average-height calculation better. A new `AnchorMode` parameter (`None`, `Beginning`, `End`) controls viewport pinning when items are added — useful for news feeds (`Beginning`) and chat / log views (`End`):

```razor
<Virtualize AnchorMode="End" Items="@messages" Context="msg">
    <MessageBubble Value="@msg" />
</Virtualize>
```

**TempData under static SSR.** A `[CascadingParameter] public ITempData? TempData { get; set; }` and a `[SupplyParameterFromTempData]` attribute persist data between HTTP requests during static server-side rendering — flash messages, POST-Redirect-GET state, one-time notifications.

**Relative navigation.** `NavigateTo` and `<NavLink>` accept `RelativeToCurrentUri = true`, resolving the target against the current path instead of the app's base URI:

```csharp
Navigation.NavigateTo("configuration",
    new NavigationOptions { RelativeToCurrentUri = true });
```

**Server-triggered circuit pause.** Server-side Blazor can ask connected clients to begin the graceful pause flow via `Circuit.RequestCircuitPauseAsync(CancellationToken)` — useful for planned shutdowns, instance draining, and maintenance windows.

**`BasePath` component and `DisplayName` component.** `<BasePath />` renders the `<base href>` tag automatically; `<DisplayName For="..." />` reads `[Display(Name=...)]` or `[DisplayName(...)]` from model metadata.

**New project template, `blazorwebworker`,** scaffolds a Blazor WebAssembly app that runs CPU-heavy work in a Web Worker so the UI thread stays responsive:

```
dotnet new blazorwebworker -o MyApp
```

### Authentication and rate limiting

ASP.NET Core Identity migrates from `DateTime`/`DateTimeOffset` to `TimeProvider`, making lockouts, token expiration, and security-stamp validation deterministic in tests via `FakeTimeProvider`. Passkey display names are inferred automatically from authenticator AAGUIDs for known providers (Google Password Manager, iCloud Keychain, Windows Hello, 1Password, Bitwarden).

`FixedWindowRateLimiter` now reports a `RetryAfter` value that reflects the next window boundary, so apps propagating that into the `Retry-After` header automatically produce accurate retry intervals.

### MCP server template ships in the box

The `mcpserver` template — for building Model Context Protocol servers — now bundles with the .NET SDK rather than requiring `Microsoft.McpServer.ProjectTemplates`:

```
dotnet new mcpserver -o MyMcpServer
```

## BCL and API additions

### Process gets the biggest update in years

`System.Diagnostics.Process` finally gets the ergonomic helpers that most teams ended up writing themselves:

```csharp
// One-shot capture of stdout/stderr plus exit code.
ProcessTextOutput result = await Process.RunAndCaptureTextAsync(
    "git", ["status", "--porcelain"]);

Console.WriteLine(result.StandardOutput);
Console.WriteLine($"Exit: {result.ExitStatus.ExitCode}");
```

The new family includes `Process.Run` / `RunAsync`, `Process.RunAndCaptureText` / `RunAndCaptureTextAsync`, `Process.ReadAllText` / `ReadAllBytes` / `ReadAllLinesAsync`, plus fire-and-forget options:

- `Process.StartAndForget` — starts a child you don't intend to wait for; the runtime detaches the handle.
- `ProcessStartInfo.StartDetached` — detaches from the parent's session/console so the child outlives a terminal.
- `ProcessStartInfo.KillOnParentExit` (Windows) — terminates the child when the parent exits.

`SafeProcessHandle` gains `Start`, `Kill`, `Signal`, `WaitForExit` / `WaitForExitAsync`, and a `ProcessId` property. `ProcessStartInfo.InheritedHandles`, `StandardInputHandle`, `StandardOutputHandle`, and `StandardErrorHandle` let you control exactly which OS handles cross the fork boundary instead of inheriting everything.

`Console` now honours the `FORCE_COLOR` standard — useful for piping coloured output through `tee` or into CI viewers.

### System.Text.Json

Several quality-of-life additions:

```csharp
var options = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.PascalCase
};

// Strongly typed metadata retrieval — no more downcast from non-generic GetTypeInfo.
JsonTypeInfo<MyRecord> info = options.GetTypeInfo<MyRecord>();
```

- `JsonNamingPolicy.PascalCase` joins the existing camelCase / snake_case / kebab-case policies.
- `[JsonNamingPolicy]` can be applied per-member to override the global policy without writing a custom converter.
- `[JsonIgnore]` is now valid at the *type* level — apply once and every member inherits the ignore condition.
- F# discriminated unions serialize out of the box, with no custom converter.
- `Utf8JsonWriter.Reset(stream, options)` accepts new writer options when repooling.

### Compression and archives

The `System.IO.Compression` namespace gains span-based `DeflateEncoder`, `ZLibEncoder`, and `GZipEncoder` types that mirror the shape of `BrotliEncoder` — encode and decode without allocating a `Stream`:

```csharp
ReadOnlySpan<byte> source = [0x48, 0x65, 0x6C, 0x6C, 0x6F];
Span<byte> destination = stackalloc byte[64];

using ZLibEncoder encoder = new();
OperationStatus status = encoder.Compress(
    source, destination,
    out int consumed, out int written,
    isFinalBlock: true);
```

Zstandard joins the namespace as `ZstandardStream` / `ZstandardEncoder`. `ZipArchiveEntry.Open(FileAccess)` and a new `CompressionMethod` property let you open entries for explicit read/write/read-write access and inspect their compression. `ZipArchive` now validates CRC32 on read — corrupt archives that previously passed silently now throw `InvalidDataException`. `DeflateStream` and `GZipStream` write format headers and footers even for empty payloads (a **behaviour change** if you depended on empty output).

`TarFile.CreateFromDirectory` accepts a `TarEntryFormat` parameter — pick `Pax`, `Ustar`, `Gnu`, or `V7` instead of always producing Pax. `TarReader` now also handles the GNU sparse 1.0 (PAX) representation.

### Strings, numerics, and low-level I/O

- `String` gains `Rune`-based overloads of `Contains`, `StartsWith` / `EndsWith`, `IndexOf` / `LastIndexOf`, `Replace`, `Split`, and `Trim*`. `Char.Equals(char, StringComparison)` brings ordinal vs. culture-aware comparisons to single characters.
- `BitConverter` adds `BFloat16` round-tripping for ML interop.
- `double`, `float`, and `Half` can format and parse in IEEE-754 hex form (`"0X1.921FB54442D18P+1"`), preserving every bit for golden-file tests and C `printf("%a", ...)` interop.
- `RegexOptions.AnyNewLine` makes `^`, `$`, and `.` treat all Unicode line terminators (`\r\n`, ``, ``, ``) as newlines, not just `\n`.
- `SafeFileHandle.Type` reports whether a handle is a file, pipe, socket, or directory without P/Invoke; `SafeFileHandle.CreateAnonymousPipe(...)` makes an anonymous pipe pair with independent async settings.
- `RandomAccess.Read` / `Write` now work with non-seekable handles like pipes.
- `BitArray.PopCount()` returns the number of set bits efficiently.
- `Utf8.IndexOfInvalidSubsequence` and `Utf16.IsValid` / `IndexOfInvalidSubsequence` let parsers report the exact byte position of an encoding error instead of bailing out with a generic exception.

### Networking and TLS

`HttpClient` automatically downgrades to HTTP/1.1 when a request needs NTLM/Negotiate authentication, which HTTP/2 doesn't allow. Enterprise intranets using Windows auth no longer need explicit `HttpRequestMessage.Version` overrides. On Linux, certificate-validation failures now emit standard TLS alerts to the peer instead of dropping the connection, matching Windows behaviour.

### Caching observability

`MemoryCache` ships with built-in OpenTelemetry-compatible metrics — no extra adapter package. Opt in by setting `TrackStatistics`:

```csharp
var cache = new MemoryCache(new MemoryCacheOptions
{
    TrackStatistics = true
});
```

The `Microsoft.Extensions.Caching.Memory.MemoryCache` meter publishes `dotnet.cache.requests` (with a `hit`/`miss` tag), `dotnet.cache.evictions`, `dotnet.cache.entries`, and `dotnet.cache.estimated_size`. A new `MemoryCache` constructor takes an `IMeterFactory` for per-instance metrics.

## SDK and tooling

- **`dotnet watch`** integrates with Aspire app hosts, recovers automatically after a crash, and supports device selection for MAUI and mobile.
- **`dotnet run -e KEY=value`** passes environment variables from the command line — no more wrapping in shell-specific syntax.
- **File-based apps** now support `#:include` so you can split a single-file app across multiple files without scaffolding a project.
- **`dotnet sln`** can create and edit solution filters (`.slnf`).
- **Smaller SDK installers** on Linux and macOS via assembly deduplication; crossgen is skipped for `DotnetTools`-only assemblies.
- **OpenTelemetry replaces Application Insights** for CLI telemetry — the SDK reports back over the open standard.
- **Foundation for a NativeAOT `dotnet` CLI entry point** lands in 11.

## Migration considerations

The shift from .NET 10 to .NET 11 is mostly a recompile, but a few items need attention.

### Updated hardware baselines

This is the change most likely to surprise you. .NET 11 raises the minimum CPU baseline:

| OS      | Previous JIT/AOT minimum | New JIT/AOT minimum | Previous R2R target | New R2R target   |
| ------- | ------------------------ | ------------------- | ------------------- | ---------------- |
| Apple   | x86-64-v1                | x86-64-v2           | x86-64-v2           | (no change)      |
| Linux   | x86-64-v1                | x86-64-v2           | x86-64-v2           | x86-64-v3        |
| Windows | x86-64-v1                | x86-64-v2           | x86-64-v2           | x86-64-v3        |
| Apple   | Apple M1                 | (no change)         | Apple M1            | (no change)      |
| Linux   | armv8.0-a                | (no change)         | armv8.0-a           | armv8.0-a + LSE  |
| Windows | armv8.0-a                | armv8.0-a + LSE     | armv8.0-a           | armv8.2-a + RCPC |

`x86-64-v2` requires `CX16`, `POPCNT`, `SSE3`, `SSSE3`, `SSE4.1`, and `SSE4.2`. In practice, anything Intel and AMD still officially support meets it — the chips that go below were last supported around 2013 — but if you build container images for older bare-metal fleets or air-gapped environments, validate before upgrading. Running .NET 11 on hardware below the baseline now fails with a startup message:

> The current CPU is missing one or more of the baseline instruction sets.

The R2R target lifting to `x86-64-v3` means precompiled images now assume AVX/AVX2/BMI/FMA. Hardware that meets the JIT baseline but not the R2R baseline will pay a small JIT cost at startup as falls back.

### Runtime Async and async behaviour

Even if you don't enable Runtime Async in your own project, the BCL and ASP.NET Core's shared-framework libraries are compiled with it. Most apps see only cleaner stack traces, but exercise your test suite, especially around `ExecutionContext` / `AsyncLocal` propagation and exception flow. The `DOTNET_RuntimeAsync` environment variable is gone — use `<UseRuntimeAsync>false</UseRuntimeAsync>` to opt out per project.

### Empty Deflate/GZip output now writes headers and footers

If you rely on `DeflateStream` or `GZipStream` producing an empty file when no data is written, that changes in .NET 11. The streams now always emit format-compliant headers and footers, which is what every other implementation already produces.

### OpenAPI 3.2 is a breaking dependency

If you use `Microsoft.AspNetCore.OpenApi`, the underlying `Microsoft.OpenApi` library jumps to 3.3.1 with breaking changes in the doc-model types. Walk the [Microsoft.OpenApi upgrade guide](https://github.com/microsoft/OpenAPI.NET/blob/main/docs/upgrade-guide-3.md) before bumping.

### ZIP CRC32 is now validated

Archives that previously passed without validation now throw `InvalidDataException` on a CRC mismatch. If your pipeline produced subtly corrupt ZIPs that nobody noticed, you will notice now — which is the point.

### Preview vs. stable surface

C# 15 (`union`, collection expression arguments) and Runtime Async are still labelled preview features in their respective designs even though Runtime Async no longer requires `<EnablePreviewFeatures>`. Production projects should pin to released previews and budget for at least one validation pass before adopting these specific features broadly. The library surface — Process API, JSON improvements, compression, MemoryCache metrics — is stable.

## In one paragraph

.NET 11 is a polishing release with one large engineering bet — Runtime Async — and a lot of small wins everywhere else. The C# 15 additions (unions, collection expression arguments) tighten the language's modelling story. The JIT, ReadyToRun, and hardware-intrinsics work shaves overhead from real workloads without you changing code. ASP.NET Core picks up Zstandard, native OpenTelemetry, and a much better Blazor `Virtualize`. The BCL finally gets a sane `Process` API and a stack of span-based encoders. The thing to watch when you upgrade is the hardware baseline lift and the OpenAPI 3.2 breaking change; everything else should just compile and run, faster and cleaner than before.
