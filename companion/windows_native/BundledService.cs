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

        // Older standalone Companion versions stored only their project
        // mapping under the user profile. Offer a copy, never move or delete
        // it, so reconnecting does not silently drop saved project IDs.
        var previous = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".montara-companion");
        var previousProjects = Path.Combine(previous, "projects.json");
        var currentProjects = Path.Combine(data, "projects.json");
        if (!File.Exists(currentProjects) && File.Exists(previousProjects))
        {
            var choice = System.Windows.Forms.MessageBox.Show(
                "Se ha encontrado una configuración anterior de Companion.\\n" +
                "¿Copiar las referencias de proyectos al nuevo Companion?\\n" +
                "No se moverán ni subirán vídeos.",
                "Montara · Conservar proyectos",
                System.Windows.Forms.MessageBoxButtons.YesNo,
                System.Windows.Forms.MessageBoxIcon.Question);
            if (choice == System.Windows.Forms.DialogResult.Yes)
            {
                File.Copy(previousProjects, currentProjects, overwrite: false);
                foreach (var name in new[] { "places.json" })
                {
                    var src = Path.Combine(previous, name);
                    var dst = Path.Combine(data, name);
                    if (File.Exists(src) && !File.Exists(dst))
                        File.Copy(src, dst, overwrite: false);
                }
            }
        }

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
