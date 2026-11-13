using System.Diagnostics;
using System.Drawing;
using System.Net.Http.Json;
using System.Text.Json;
using System.Windows.Forms;

namespace Montara.Companion;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new CompanionTray());
    }
}

internal sealed record LocalConfiguration(string PythonExe, string CompanionScript)
{
    private static string SettingsPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Montara", "Companion", "launcher-settings.json");

    internal static LocalConfiguration? Load()
    {
        try
        {
            if (!File.Exists(SettingsPath)) return null;
            var config = JsonSerializer.Deserialize<LocalConfiguration>(File.ReadAllText(SettingsPath));
            return config is not null && File.Exists(config.PythonExe) &&
                File.Exists(config.CompanionScript) ? config : null;
        }
        catch (JsonException) { return null; }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }

    internal void Save()
    {
        var dir = Path.GetDirectoryName(SettingsPath)!;
        Directory.CreateDirectory(dir);
        var temp = SettingsPath + ".new";
        File.WriteAllText(temp, JsonSerializer.Serialize(this));
        File.Move(temp, SettingsPath, true);
    }
}

internal sealed class CompanionTray : ApplicationContext
{
    private readonly NotifyIcon _tray;
    private readonly Icon _brandIcon;
    private readonly ToolStripMenuItem _startItem;
    private readonly ToolStripMenuItem _statusItem;
    private readonly ToolStripMenuItem _updateItem;
    private readonly HttpClient _client = new() { Timeout = TimeSpan.FromSeconds(6) };
    private LocalConfiguration? _config;
    private Process? _started;

    internal CompanionTray()
    {
        _config = LocalConfiguration.Load();
        var menu = new ContextMenuStrip();
        _statusItem = new ToolStripMenuItem("Estado de Companion", null,
            async (_, _) => await ShowStatusAsync());
        _startItem = new ToolStripMenuItem("Iniciar Companion", null,
            async (_, _) => await StartCompanionAsync());
        var configure = new ToolStripMenuItem("Configurar Companion…", null,
            (_, _) => Configure());
        _updateItem = new ToolStripMenuItem("Buscar actualizaciones…", null,
            (_, _) => ShowUpdateInformation());
        var fixRender = new ToolStripMenuItem("Instalar corrección de render…", null,
            async (_, _) => await ApplyRenderFixAsync());
        var exit = new ToolStripMenuItem("Cerrar icono de Montara", null, (_, _) => ExitThread());

        menu.Items.AddRange([_statusItem, _startItem, configure,
            fixRender, new ToolStripSeparator(), _updateItem,
            new ToolStripSeparator(), exit]);

        _brandIcon = MontaraIcon.Create();
        _tray = new NotifyIcon
        {
            Icon = _brandIcon,
            Text = "Montara Companion",
            Visible = true,
            ContextMenuStrip = menu
        };
        _tray.DoubleClick += async (_, _) => await ShowStatusAsync();
    }

    private async Task<bool> IsCompanionRunningAsync()
    {
        try
        {
            using var response = await _client.GetAsync(
                "http://127.0.0.1:47820/health",
                HttpCompletionOption.ResponseHeadersRead);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException) { return false; }
        catch (TaskCanceledException) { return false; }
    }

    private async Task ShowStatusAsync()
    {
        _statusItem.Enabled = false;
        try
        {
            var connected = await IsCompanionRunningAsync();
            MessageBox.Show(connected
                    ? "Companion responde en localhost:47820."
                    : "Companion no está conectado. Puedes iniciarlo desde el menú.",
                "Montara Companion", MessageBoxButtons.OK,
                connected ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
        }
        finally { _statusItem.Enabled = true; }
    }

    private void Configure()
    {
        using var python = new OpenFileDialog
        {
            Title = "Selecciona el python.exe de tu Companion actual",
            Filter = "Python|python.exe",
            CheckFileExists = true
        };
        if (python.ShowDialog() != DialogResult.OK) return;

        using var script = new OpenFileDialog
        {
            Title = "Selecciona el companion.py que ya utilizabas",
            Filter = "Companion|companion.py",
            CheckFileExists = true
        };
        if (script.ShowDialog() != DialogResult.OK) return;

        _config = new LocalConfiguration(python.FileName, script.FileName);
        try
        {
            _config.Save();
            MessageBox.Show("Rutas guardadas. No se han movido archivos ni vídeos.",
                "Montara Companion");
        }
        catch (IOException e)
        {
            MessageBox.Show("No se pudo guardar la configuración: " + e.Message,
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        catch (UnauthorizedAccessException e)
        {
            MessageBox.Show("Acceso denegado al guardar: " + e.Message,
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task StartCompanionAsync()
    {
        _startItem.Enabled = false;
        try
        {
            if (await IsCompanionRunningAsync())
            {
                MessageBox.Show("Companion ya está ejecutándose. No se abrirá otra instancia.",
                    "Montara Companion");
                return;
            }

            if (_config is null)
            {
                Configure();
                if (_config is null) return;
            }

            if (!File.Exists(_config.PythonExe) || !File.Exists(_config.CompanionScript))
            {
                MessageBox.Show("No se encuentran los archivos. Revisa Configurar Companion.",
                    "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            var start = new ProcessStartInfo(_config.PythonExe)
            {
                WorkingDirectory = Path.GetDirectoryName(_config.CompanionScript)!,
                UseShellExecute = false,
                CreateNoWindow = false
            };
            start.ArgumentList.Add(_config.CompanionScript);
            _started = Process.Start(start);
            if (_started is null) throw new InvalidOperationException("No se inició Python.");
        }
        catch (Exception e) when (e is IOException or System.ComponentModel.Win32Exception
                                  or InvalidOperationException)
        {
            MessageBox.Show("No se pudo iniciar Companion: " + e.Message,
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { _startItem.Enabled = true; }
    }

    private async Task ApplyRenderFixAsync()
    {
        if (await IsCompanionRunningAsync())
        {
            MessageBox.Show(
                "Cierra primero el proceso de Companion. No se interrumpirá ningún render activo.",
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        MessageBox.Show(RenderPatch.DescribeAndApply(), "Montara Companion",
            MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private void ShowUpdateInformation()
    {
        // The old beta scripts were removed from the release channel after
        // Windows Defender detected Trojan:Script/Wacatac.B!ml.
        // This native host DOES NOT download or execute code.
        // A future release will delegate installs to Windows' trusted,
        // publisher-signed package/update mechanism.
        MessageBox.Show(
            "Canal de actualización firmado todavía no configurado.\n\n" +
            "No se descargará ni ejecutará ningún archivo. " +
            "Los instaladores deberán tener firma válida antes de activar esta función.",
            "Actualizaciones de Montara", MessageBoxButtons.OK,
            MessageBoxIcon.Information);
    }

    protected override void ExitThreadCore()
    {
        // Never terminate a rendering Companion automatically.
        // Closing the tray icon does not terminate processes or change files.
        _tray.Visible = false;
        _tray.Dispose();
        _brandIcon.Dispose();
        _client.Dispose();
        _started?.Dispose();
        base.ExitThreadCore();
    }
}
