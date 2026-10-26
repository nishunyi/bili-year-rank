using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows.Forms;

internal static class Launcher {
    private const string Releases="https://github.com/nishunyi/bili-year-rank/releases";

    private static bool Compatible(string root) {
        string resources=Path.Combine(root,"resources");
        string expected=File.ReadAllText(Path.Combine(resources,"year-rank","bootstrap.sha256")).Trim();
        string actual;
        using(var hash=SHA256.Create())
        using(var stream=File.OpenRead(Path.Combine(resources,"app.asar")))
            actual=BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
        return String.Equals(expected,actual,StringComparison.OrdinalIgnoreCase)
            && File.ReadAllText(Path.Combine(root,"versions",".version")).Trim()=="1.19.0";
    }

    [STAThread]
    private static int Main(string[] args) {
        string root=AppDomain.CurrentDomain.BaseDirectory;
        bool compatible=false;
        try {compatible=Compatible(root);} catch(IOException) {} catch(UnauthorizedAccessException) {}
        if(args.Length==1 && args[0]=="--check") return compatible ? 0 : 2;
        string client=Path.Combine(root,"哔哩哔哩.exe");
        if(!File.Exists(client)) {
            MessageBox.Show("客户端文件缺失，请重新解压完整包或重新安装。","年度榜增强版",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 3;
        }
        if(!compatible) {
            var answer=MessageBox.Show("检测到客户端文件或运行资源已变化，可能是官方更新覆盖了年度榜入口。\n\n当前版本的年度榜兼容性尚未验证，原版功能仍可尝试使用。请从项目发布页获取适配版本。\n\n是否打开发布页？\n“是”：打开发布页；“否”：继续启动客户端；“取消”：退出。",
                "年度榜需要适配更新",MessageBoxButtons.YesNoCancel,MessageBoxIcon.Information,MessageBoxDefaultButton.Button1);
            if(answer==DialogResult.Cancel) return 2;
            if(answer==DialogResult.Yes) Process.Start(new ProcessStartInfo(Releases){UseShellExecute=true});
        }
        try {
            Process.Start(new ProcessStartInfo(client){WorkingDirectory=root,UseShellExecute=true});
            return 0;
        } catch(Exception error) {
            MessageBox.Show("无法启动客户端："+error.Message,"年度榜增强版",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
