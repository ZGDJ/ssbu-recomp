# The worker waits for a gate until it belongs to this job. All descendants inherit
# the job, so cancellation or a crashed wizard cannot leave compilers writing files.
if (-not ('OpenSmash.SetupJob' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
namespace OpenSmash {
    public sealed class SetupJob : IDisposable {
        [StructLayout(LayoutKind.Sequential)] struct Basic {
            public long ProcessTime, JobTime;
            public uint Flags;
            public UIntPtr MinWorking, MaxWorking;
            public uint ActiveLimit;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }
        [StructLayout(LayoutKind.Sequential)] struct Io {
            public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        }
        [StructLayout(LayoutKind.Sequential)] struct Extended {
            public Basic Basic;
            public Io Io;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        static extern IntPtr CreateJobObject(IntPtr security, string name);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool SetInformationJobObject(IntPtr job, int kind, ref Extended info, uint length);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool TerminateJobObject(IntPtr job, uint code);
        [StructLayout(LayoutKind.Sequential)] struct Accounting {
            public long UserTime, KernelTime, PeriodUserTime, PeriodKernelTime;
            public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
        }
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool QueryInformationJobObject(IntPtr job, int kind, ref Accounting info, uint length, IntPtr returned);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        IntPtr handle;
        public SetupJob() {
            handle = CreateJobObject(IntPtr.Zero, null);
            if (handle == IntPtr.Zero) throw new Win32Exception();
            Extended limits = new Extended();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(handle, 9, ref limits, (uint)Marshal.SizeOf(limits))) {
                int error = Marshal.GetLastWin32Error(); Dispose(); throw new Win32Exception(error);
            }
        }
        public void Attach(IntPtr process) {
            if (!AssignProcessToJobObject(handle, process)) throw new Win32Exception();
        }
        public void Cancel() {
            if (handle != IntPtr.Zero && !TerminateJobObject(handle, 1223)) throw new Win32Exception();
        }
        public bool IsEmpty {
            get {
                Accounting info = new Accounting();
                if (!QueryInformationJobObject(handle, 1, ref info, (uint)Marshal.SizeOf(info), IntPtr.Zero)) throw new Win32Exception();
                return info.ActiveProcesses == 0;
            }
        }
        public void Dispose() {
            if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; }
            GC.SuppressFinalize(this);
        }
        ~SetupJob() { Dispose(); }
    }
}
'@
}

function Test-SetupFolder([string]$Repo) {
    $resolved = [IO.Path]::GetFullPath($Repo)
    for ($item = Get-Item -LiteralPath $resolved; $null -ne $item; $item = $item.Parent) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Use a local folder without links or junctions, such as C:\OpenSmash.' }
    }
    $probe = Join-Path $resolved ('.setup-write-' + [Guid]::NewGuid().ToString('N'))
    try { [IO.File]::WriteAllText($probe, 'write test') }
    catch { throw 'Setup cannot write to this folder. Move OpenSmash to a short, writable folder, then reopen setup. Do not run as administrator just to bypass this error.' }
    finally { if (Test-Path -LiteralPath $probe) { Remove-Item -LiteralPath $probe -Force } }
    $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($resolved))
    if ($drive.AvailableFreeSpace -lt 1GB) { throw 'Less than 1 GB free on the installation drive. Free space before starting setup. The full installation needs roughly 30 GB beyond the ZIP.' }
}
