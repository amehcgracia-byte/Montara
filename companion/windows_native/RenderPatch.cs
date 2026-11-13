using System.Security.Cryptography;
using System.Windows.Forms;

namespace Montara.Companion;

/// <summary>
/// Opt-in repair for the specific observed Windows WinError 5 in progress.json.
/// No general-purpose updater: it touches one known file after exact SHA checks.
/// </summary>
internal static class RenderPatch
{
    private const string ExpectedOriginalSha256 =
        "b225e473e5dfd0e3173abe44267a46de2da05819650b4f8ea5b8f1d41afca7fc";
    private const string ExpectedFixedSha256 =
        "d547858a3959c7ca59e0d3d4892dd12a14d5f23ce88527f527a3b6106b606d13";

    internal static string DescribeAndApply()
    {
        string target = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "MontaraSMARTBeta", "video", "local_video.py");

        string source = Path.Combine(
            AppContext.BaseDirectory, "render-patch", "local_video.py");

        if (!File.Exists(target))
            return "No se encontró el render de Companion existente. No se ha modificado nada.";
        if (!File.Exists(source) || !HasSha(source, ExpectedFixedSha256))
            return "La corrección incluida no coincide con la versión revisada. Instalación cancelada.";

        if (HasSha(target, ExpectedFixedSha256))
            return "El arreglo WinError 5 ya está instalado. No se ha modificado nada.";

        if (!HasSha(target, ExpectedOriginalSha256))
            return "Tu render local es de otra versión. No lo sustituiré; hay que revisar esa instalación.";

        var confirm = MessageBox.Show(
            "Montara actualizará solo el indicador de progreso de render Windows.\n" +
            "Se conservarán el Engine, FFmpeg, los originales y los proyectos.\n" +
            "Se guardará una copia del archivo anterior.\n\n¿Aplicar corrección?",
            "Montara · Corregir render",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question);

        if (confirm != DialogResult.Yes) return "Instalación cancelada sin cambios.";

        string backup = target + ".montara-before-progress-fix.bak";
        string staged = target + ".montara-patch-new";
        if (File.Exists(backup) || File.Exists(staged))
            return "Existe una copia o archivo temporal anterior. No se sobrescribirá; revisa el estado.";

        try
        {
            File.Copy(target, backup, overwrite: false);
            File.Copy(source, staged, overwrite: false);
            if (!HasSha(staged, ExpectedFixedSha256))
                throw new IOException("La corrección copiada no conserva su hash.");

            File.Move(staged, target, overwrite: true);
            return "Arreglo WinError 5 instalado. Original conservado en una copia .bak.";
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            try
            {
                if (File.Exists(staged)) File.Delete(staged);
                if (File.Exists(backup) && !HasSha(target, ExpectedOriginalSha256) &&
                    !HasSha(target, ExpectedFixedSha256))
                {
                    File.Copy(backup, target, overwrite: true);
                }
            }
            catch (IOException) { /* Leave backup for manual recovery. */ }
            catch (UnauthorizedAccessException) { /* Leave backup for manual recovery. */ }
            return "No se pudo instalar el parche: " + ex.Message +
                   ". La copia del archivo original se conserva cuando fue posible.";
        }
    }

    private static bool HasSha(string file, string expected)
    {
        using var input = File.OpenRead(file);
        return Convert.ToHexString(SHA256.HashData(input))
            .Equals(expected, StringComparison.OrdinalIgnoreCase);
    }
}
