using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;

namespace Montara.Companion;

/// <summary>
/// Montara's existing five-bar mark, reproduced from web/index.html
/// (off-white bars; centre coral). Small-size legible native tray icon.
/// No untrusted image files or downloads are needed at runtime.
/// </summary>
internal static class MontaraIcon
{
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyIcon(IntPtr handle);

    internal static Icon Create()
    {
        using var canvas = new Bitmap(64, 64);
        using (var g = Graphics.FromImage(canvas))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);

            using var back = new SolidBrush(Color.FromArgb(12, 12, 15));
            using var outline = new Pen(Color.FromArgb(53, 54, 60), 1.5f);
            using var rounded = new GraphicsPath();
            // Explicit arcs work on net8.0-windows (AddRoundedRectangle is
            // only available in newer WinForms frameworks).
            const float edge = 1f, span = 62f, radius = 14f;
            const float diameter = radius * 2f;
            rounded.AddArc(edge, edge, diameter, diameter, 180, 90);
            rounded.AddArc(edge + span - diameter, edge, diameter, diameter, 270, 90);
            rounded.AddArc(edge + span - diameter, edge + span - diameter,
                           diameter, diameter, 0, 90);
            rounded.AddArc(edge, edge + span - diameter, diameter, diameter, 90, 90);
            rounded.CloseFigure();
            g.FillPath(back, rounded);
            g.DrawPath(outline, rounded);

            // The original Montara identity: five rounded vertical bars,
            // centre bar in #FF4F2E; proportions adapted for a 16px tray.
            int[] x = [11, 22, 32, 42, 53];
            int[] heights = [38, 28, 17, 28, 38];
            for (int i = 0; i < x.Length; i++)
            {
                using var pen = new Pen(i == 2
                    ? Color.FromArgb(255, 79, 46)
                    : Color.FromArgb(245, 243, 239), 6.5f)
                {
                    StartCap = LineCap.Round,
                    EndCap = LineCap.Round
                };
                var y = (64 - heights[i]) / 2;
                g.DrawLine(pen, x[i], y, x[i], y + heights[i]);
            }
        }

        var handle = canvas.GetHicon();
        try
        {
            using var source = Icon.FromHandle(handle);
            return (Icon)source.Clone();
        }
        finally { DestroyIcon(handle); }
    }
}
