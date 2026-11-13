using System.Diagnostics;

namespace Montara.Companion;

/// <summary>
/// First-class bundled Companion service. The operator never selects Python.
/// Engine runtime and user projects remain outside the MSIX package.
/// </summary>
internal static class BundledService
{
    internal static string Executable => Path.Combine(
        AppContext.BaseDirectory, "service", "Montara.Companion.Service.exe");

    internal static bool Available => File.Exists(Executable);

    internal static Process Start()
    {
        if (!Available)
            throw new FileNotFoundException(
                "No se encuentra el servicio local empaquetado. No se iniciará una versión parcial.",
                Executable);

        var data = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "MontaraSMARTBeta");
        Directory.CreateDirectory(data);

        var start = new ProcessStartInfo(Executable)
        {
            WorkingDirectory = data,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        start.Environment["MONTARA_COMPANION_HOME"] = data;

        // Only these HTTPS beta origins and localhost may contact the service.
        // Browser preflight requests still require Companion origin validation.
        start.Environment["MONTARA_COMPANION_ORIGINS"] =
            @"https://montara-owner-h4\.memoriainvalida001\.workers\.dev" +
            @"|https://montara-owner\.memoriainvalida001\.workers\.dev" +
            @"|https?://(localhost|127\.0\.0\.1)(:\d+)?";

        return Process.Start(start) ?? throw new IOException("No se pudo iniciar el servicio.");
    }
}
