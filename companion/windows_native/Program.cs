using System.Diagnostics;
using System.Drawing;
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

internal sealed class CompanionTray : ApplicationContext
{
    private readonly NotifyIcon _tray;
    private readonly Icon _brandIcon;
    private readonly HttpClient _client = new() { Timeout = TimeSpan.FromSeconds(5) };
    private CompanionDashboard? _dashboard;
    private Process? _service;

    internal CompanionTray()
    {
        _brandIcon = MontaraIcon.Create();
        var menu = new ContextMenuStrip();
        menu.Items.Add(new ToolStripMenuItem("Abrir Montara Companion", null,
            (_, _) => ShowDashboard()));
        menu.Items.Add(new ToolStripMenuItem("Iniciar servicio local", null,
            async (_, _) => await StartServiceAsync()));
        menu.Items.Add(new ToolStripMenuItem("Estado de conexión", null,
            async (_, _) => await ShowStatusAsync()));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(new ToolStripMenuItem("Buscar actualizaciones…", null,
            (_, _) => ShowDashboard()));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(new ToolStripMenuItem("Cerrar icono de Montara", null,
            (_, _) => ExitThread()));

        _tray = new NotifyIcon
        {
            Icon = _brandIcon,
            Text = "Montara Companion",
            Visible = true,
            ContextMenuStrip = menu
        };
        _tray.DoubleClick += (_, _) => ShowDashboard();

        // Open a proper branded window on first launch; the tray remains
        // available after the user closes it.
        ShowDashboard();
    }

    private void ShowDashboard()
    {
        if (_dashboard is not null && !_dashboard.IsDisposed)
        {
            _dashboard.Show();
            _dashboard.WindowState = FormWindowState.Normal;
            _dashboard.Activate();
            return;
        }

        _dashboard = new CompanionDashboard(_brandIcon,
            startService: StartServiceAsync,
            getStatus: ReadStatusAsync,
            repairRender: ApplyRenderFixAsync);
        _dashboard.FormClosed += (_, _) => _dashboard = null;
        _dashboard.Show();
    }

    private async Task<LocalStatus> ReadStatusAsync()
    {
        try
        {
            using var response = await _client.GetAsync(
                "http://127.0.0.1:47820/health",
                HttpCompletionOption.ResponseContentRead);
            if (!response.IsSuccessStatusCode) return LocalStatus.Disconnected;
            using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var payload = json.RootElement;
            if (!payload.TryGetProperty("app", out var app) ||
                app.GetString() != "montara-companion")
                return LocalStatus.Disconnected;

            string version = payload.TryGetProperty("version", out var v) &&
                v.ValueKind == JsonValueKind.String ? v.GetString() ?? "?" : "?";
            bool busy = payload.TryGetProperty("busy", out var b) &&
                b.ValueKind == JsonValueKind.True;
            bool renderer = payload.TryGetProperty("local_video", out var e) &&
                e.ValueKind == JsonValueKind.Object;
            return new LocalStatus(true, busy, renderer, version);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or
                                   JsonException or IOException)
        {
            return LocalStatus.Disconnected;
        }
    }

    private async Task ShowStatusAsync()
    {
        var status = await ReadStatusAsync();
        MessageBox.Show(status.Connected
                ? $"Companion {status.Version} conectado.\n" +
                  (status.Busy ? "Trabajo activo: no actualizar." : "Libre para trabajar.")
                : "Companion no está conectado. Abre Montara para iniciar el servicio.",
            "Montara Companion", MessageBoxButtons.OK,
            status.Connected ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }

    private async Task StartServiceAsync()
    {
        var status = await ReadStatusAsync();
        if (status.Connected)
        {
            MessageBox.Show("Companion ya está en marcha. No se abrirá otra instancia.",
                "Montara Companion");
            return;
        }
        try
        {
            // Fully bundled service: never ask the user to select python.exe
            // or companion.py; no downloading or executing scripts.
            _service = BundledService.Start();
            await Task.Delay(550);
            if (_service.HasExited)
                throw new InvalidOperationException(
                    "El servicio local terminó al arrancar. Comprueba FFmpeg y el runtime de vídeo.");
        }
        catch (Exception ex) when (ex is FileNotFoundException or IOException or
                                   System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            MessageBox.Show("No se pudo iniciar Companion: " + ex.Message,
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        if (_dashboard is not null && !_dashboard.IsDisposed)
            await _dashboard.RefreshStatusAsync();
    }

    private async Task ApplyRenderFixAsync()
    {
        var status = await ReadStatusAsync();
        if (status.Connected)
        {
            MessageBox.Show("Cierra primero el servicio Companion. " +
                            "No se detendrán renders ni procesos automáticamente.",
                "Montara Companion", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var result = RenderPatch.DescribeAndApply();
        MessageBox.Show(result, "Montara · Corrección de render",
            MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    protected override void ExitThreadCore()
    {
        // The local video service may have a job in progress: closing the tray
        // must never terminate it. Jobs and their files survive.
        if (_dashboard is not null && !_dashboard.IsDisposed) _dashboard.Close();
        _tray.Visible = false;
        _tray.Dispose();
        _brandIcon.Dispose();
        _client.Dispose();
        _service?.Dispose();
        base.ExitThreadCore();
    }
}

internal sealed record LocalStatus(bool Connected, bool Busy, bool RenderReady, string Version)
{
    internal static readonly LocalStatus Disconnected = new(false, false, false, "");
}

internal sealed class CompanionDashboard : Form
{
    private static readonly Color Coal = Color.FromArgb(16, 16, 20);
    private static readonly Color Panel = Color.FromArgb(31, 31, 36);
    private static readonly Color Ivory = Color.FromArgb(245, 243, 239);
    private static readonly Color Muted = Color.FromArgb(169, 170, 177);
    private static readonly Color Coral = Color.FromArgb(255, 79, 46);

    private readonly Func<Task> _start;
    private readonly Func<Task<LocalStatus>> _status;
    private readonly Func<Task> _repair;
    private readonly Label _statusLabel;
    private readonly Label _subLabel;
    private readonly Button _startButton;
    private readonly Button _repairButton;

    internal CompanionDashboard(Icon icon,
        Func<Task> startService,
        Func<Task<LocalStatus>> getStatus,
        Func<Task> repairRender)
    {
        _start = startService;
        _status = getStatus;
        _repair = repairRender;

        Text = "Montara Companion";
        Icon = icon;
        BackColor = Coal;
        ForeColor = Ivory;
        ClientSize = new Size(462, 455);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 10f);
        AutoScaleMode = AutoScaleMode.Dpi;

        var logo = new PictureBox
        {
            Image = icon.ToBitmap(),
            SizeMode = PictureBoxSizeMode.Zoom,
            Location = new Point(24, 24),
            Size = new Size(55, 55),
            BackColor = Coal
        };
        Controls.Add(logo);
        Controls.Add(TextLabel("MONTARA", 90, 22, 322, 38,
            new Font("Segoe UI", 23f, FontStyle.Bold), Ivory));
        Controls.Add(TextLabel("COMPANION  ·  BETA WINDOWS", 94, 63, 325, 26,
            new Font("Segoe UI", 9f, FontStyle.Bold), Coral));

        var line = new Panel
        {
            Location = new Point(24, 104),
            Size = new Size(414, 1),
            BackColor = Color.FromArgb(56, 56, 63)
        };
        Controls.Add(line);

        var card = new Panel
        {
            Location = new Point(24, 125),
            Size = new Size(414, 111),
            BackColor = Panel
        };
        _statusLabel = TextLabel("Comprobando servicio…", 16, 17, 380, 35,
            new Font("Segoe UI", 14f, FontStyle.Bold), Ivory);
        _subLabel = TextLabel("Tus originales permanecen en este equipo.", 16, 58,
            390, 42, new Font("Segoe UI", 9f), Muted);
        card.Controls.Add(_statusLabel);
        card.Controls.Add(_subLabel);
        Controls.Add(card);

        _startButton = ActionButton("INICIAR COMPANION", 24, 258, 414, Coral, Coal);
        _startButton.Click += async (_, _) =>
        {
            _startButton.Enabled = false;
            try { await _start(); } finally
            {
                _startButton.Enabled = true;
                await RefreshStatusAsync();
            }
        };
        Controls.Add(_startButton);

        _repairButton = ActionButton("CORREGIR RENDER LOCAL", 24, 311, 201, Panel, Ivory);
        _repairButton.Click += async (_, _) =>
        {
            await _repair();
            await RefreshStatusAsync();
        };
        Controls.Add(_repairButton);

        var update = ActionButton("BUSCAR ACTUALIZACIONES", 237, 311, 201, Panel, Ivory);
        update.Click += (_, _) => MessageBox.Show(
            "El canal de actualizaciones firmadas está en preparación.\n\n" +
            "No descargaremos ni ejecutaremos software sin una firma de confianza.",
            "Montara · Actualizaciones", MessageBoxButtons.OK,
            MessageBoxIcon.Information);
        Controls.Add(update);

        Controls.Add(TextLabel("H4  ·  Originales locales  ·  Sin subidas de vídeo", 24, 384, 420, 24,
            new Font("Segoe UI", 9f), Muted));
        Controls.Add(TextLabel("Cerrar esta ventana no interrumpe los renders.", 24, 412, 420, 22,
            new Font("Segoe UI", 9f), Muted));

        Shown += async (_, _) => await RefreshStatusAsync();
    }

    internal async Task RefreshStatusAsync()
    {
        if (IsDisposed) return;
        LocalStatus state = await _status();
        if (IsDisposed) return;

        _statusLabel.Text = state.Connected
            ? state.Busy ? "●  Procesando vídeo" : "●  Companion conectado"
            : "○  Servicio desconectado";
        _statusLabel.ForeColor = state.Connected ? Coral : Ivory;
        _subLabel.Text = state.Connected
            ? $"Versión {state.Version}   ·   " +
              (state.RenderReady ? "Motor local detectado" : "Motor local sin verificar")
            : "Pulsa Iniciar para conectar el servicio local.";
        _startButton.Enabled = !state.Connected;
        _repairButton.Enabled = !state.Connected;
    }

    private static Label TextLabel(string text, int x, int y, int width, int height,
        Font font, Color color) => new()
        {
            Text = text,
            Location = new Point(x, y),
            Size = new Size(width, height),
            Font = font,
            ForeColor = color,
            AutoSize = false
        };

    private static Button ActionButton(string text, int x, int y, int width,
        Color background, Color foreground)
    {
        return new Button
        {
            Text = text,
            Location = new Point(x, y),
            Size = new Size(width, 42),
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            BackColor = background,
            ForeColor = foreground,
            FlatStyle = FlatStyle.Flat,
            UseVisualStyleBackColor = false,
            Cursor = Cursors.Hand
        };
    }
}
