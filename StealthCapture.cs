using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

namespace StealthCapture
{
    #region Raw vtable delegates (cached globally)

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int QIDel(IntPtr pThis, ref Guid riid, out IntPtr ppvObject);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate uint AddRefDel(IntPtr pThis);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate uint ReleaseDel(IntPtr pThis);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int EnumAdapters1Del(IntPtr pThis, uint Adapter, out IntPtr ppAdapter);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int EnumOutputsDel(IntPtr pThis, uint Output, out IntPtr ppOutput);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int DuplicateOutputDel(IntPtr pThis, IntPtr pDevice, out IntPtr ppOutputDuplication);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int AcquireNextFrameDel(IntPtr pThis, uint Timeout, out DXGI_OUTDUPL_FRAME_INFO fi, out IntPtr ppDesktopResource);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int ReleaseFrameDel(IntPtr pThis);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate void GetDescDel(IntPtr pThis, out DXGI_OUTDUPL_DESC pDesc);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int CreateTexture2DDel(IntPtr pThis, ref D3D11_TEX2D_DESC pDesc, IntPtr pInitialData, out IntPtr ppTexture2D);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int MapDel(IntPtr pThis, IntPtr pResource, uint Subresource, uint MapType, uint MapFlags, out D3D11_MAPPED_SUBRESOURCE pMappedResource);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate void UnmapDel(IntPtr pThis, IntPtr pResource, uint Subresource);

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate void CopyResourceDel(IntPtr pThis, IntPtr pDstResource, IntPtr pSrcResource);

    #endregion

    #region Structs (Blittable, no GC alloc when stack-allocated)

    [StructLayout(LayoutKind.Sequential)]
    struct DXGI_OUTDUPL_DESC { public long W, H; long _a, _b; int Fmt, _c, _d; int Rot, Mem; }

    [StructLayout(LayoutKind.Sequential)]
    struct DXGI_OUTDUPL_FRAME_INFO { long _a, _b; uint _c; int _d, _e; long _f, _g; uint _h, _i; }

    [StructLayout(LayoutKind.Sequential)]
    struct D3D11_TEX2D_DESC { public uint W, H, Mip, Arr; public int Fmt; public DXGI_SAMPLE_DESC Samp; public uint Usage, Bind, CPU, Misc; }

    [StructLayout(LayoutKind.Sequential)]
    struct DXGI_SAMPLE_DESC { public uint C, Q; }

    [StructLayout(LayoutKind.Sequential)]
    struct D3D11_MAPPED_SUBRESOURCE { public IntPtr pData; public uint RowPitch, DepthPitch; }

    #endregion

    public static class Capture
    {
        // ==================== Globals (singleton, init once) ====================
        private static readonly Guid IID_IDXGIFactory1 = new Guid("770aae78-f26f-4dba-a829-253c83d1b387");
        private static readonly Guid IID_IDXGIAdapter1 = new Guid("29038f61-3839-41c6-91af-474d4ef2fb4c");

        private static readonly object _lock = new object();
        private static bool _initialized;

        // DXGI/D3D resources
        private static IntPtr _pFactory, _pDevice, _pContext, _pDup, _pStaging;
        private static int _lastW, _lastH;
        private static bool _dxgiOk;

        // Cached vtable delegates
        private static EnumAdapters1Del _enumAdapters1;
        private static EnumOutputsDel _enumOutputs;
        private static DuplicateOutputDel _dupOutput;
        private static AcquireNextFrameDel _acquireFrame;
        private static ReleaseFrameDel _releaseFrame;
        private static GetDescDel _getDesc;
        private static CreateTexture2DDel _createTex2D;
        private static MapDel _map;
        private static UnmapDel _unmap;
        private static CopyResourceDel _copyResource;
        private static QIDel _qi;
        private static AddRefDel _addRef;
        private static ReleaseDel _release;

        // Pre-allocated pixel buffer (max size for all screens)
        private static byte[] _frameBuf;
        private static int _bufW, _bufH;

        // GDI canvas cache
        private static System.Drawing.Bitmap _gdiCanvas;
        private static System.Drawing.Graphics _gdiGraphics;
        private static int _gdiW, _gdiH;

        private const int S_OK = 0;
        private const int W_TIMEOUT = unchecked((int)0x887A0027);
        private const int ACCESS_LOST = unchecked((int)0x887A0026);
        private const int D3D_FEATURE_LEVEL_11_0 = 0xB000;
        private const uint CREATE_BGRA = 0x20;
        private const int FMT_B8G8R8A8 = 87;
        private const uint STAGING = 3, CPU_READ = 0x20000, MAP_READ = 1;

        // ==================== Native Imports ====================

        [DllImport("dxgi.dll")]
        static extern int CreateDXGIFactory1(ref Guid riid, out IntPtr ppFactory);

        [DllImport("d3d11.dll")]
        static extern int D3D11CreateDevice(IntPtr pAdapter, int DriverType, IntPtr Software, uint Flags,
            [In] int[] pFeatureLevels, uint FeatureLevels, uint SDKVersion,
            out IntPtr ppDevice, out int pFeatureLevel, out IntPtr ppImmediateContext);

        [DllImport("kernel32.dll", EntryPoint = "RtlMoveMemory")]
        static extern void RtlMoveMemory(IntPtr dest, IntPtr src, uint length);

        // ==================== VTable Helpers ====================

        static T ReadVtbl<T>(IntPtr pUnk, int slot) where T : class
        {
            IntPtr vtable = Marshal.ReadIntPtr(pUnk);
            IntPtr fp = Marshal.ReadIntPtr(vtable + slot * IntPtr.Size);
            return Marshal.GetDelegateForFunctionPointer(fp, typeof(T)) as T;
        }

        static void Hr(int hr, string msg) { if (hr != S_OK) throw new Exception(msg + " HR=0x" + hr.ToString("X8")); }

        // ==================== DXGI Init (called once, reused globally) ====================

        static void InitDxgi()
        {
            lock (_lock)
            {
                if (_initialized) return;

                try
                {
                    // 1) Factory
                    Guid iidF = IID_IDXGIFactory1;
                    Hr(CreateDXGIFactory1(ref iidF, out _pFactory), "CreateDXGIFactory1");
                    _qi = ReadVtbl<QIDel>(_pFactory, 0);
                    _addRef = ReadVtbl<AddRefDel>(_pFactory, 1);
                    _release = ReadVtbl<ReleaseDel>(_pFactory, 2);

                    // 2) EnumAdapters1 (vtable slot 12: 3 IUnknown + 4 IDXGIObject + 5 IDXGIFactory)
                    //    Returns IDXGIAdapter1 directly — no QI needed
                    _enumAdapters1 = ReadVtbl<EnumAdapters1Del>(_pFactory, 12);
                    IntPtr pAdapter1;
                    int hr = _enumAdapters1(_pFactory, 0, out pAdapter1);
                    if (hr != S_OK)
                    {
                        // Try adapter 1 if 0 fails (laptop with dGPU)
                        hr = _enumAdapters1(_pFactory, 1, out pAdapter1);
                        Hr(hr, "EnumAdapters1(1)");
                    }

                    // 3) EnumOutputs (vtable slot 7: 3 IUnknown + 4 IDXGIObject)
                    _enumOutputs = ReadVtbl<EnumOutputsDel>(pAdapter1, 7);
                    IntPtr pOutput;
                    hr = _enumOutputs(pAdapter1, 0, out pOutput);
                    if (hr != S_OK)
                    {
                        hr = _enumOutputs(pAdapter1, 1, out pOutput);
                        Hr(hr, "EnumOutputs(1)");
                    }

                    // 4) D3D11 device
                    int[] fl = { D3D_FEATURE_LEVEL_11_0 }; int gotFl;
                    Hr(D3D11CreateDevice(pAdapter1, 0, IntPtr.Zero, CREATE_BGRA, fl, 1, 7,
                        out _pDevice, out gotFl, out _pContext), "D3D11CreateDevice");

                    // Cache D3D11 vtable delegates
                    _createTex2D = ReadVtbl<CreateTexture2DDel>(_pDevice, 5);   // slot 5
                    _map = ReadVtbl<MapDel>(_pContext, 10);                     // slot 10
                    _unmap = ReadVtbl<UnmapDel>(_pContext, 11);                // slot 11
                    _copyResource = ReadVtbl<CopyResourceDel>(_pContext, 43);  // slot 43

                    // 5) DuplicateOutput (IDXGIOutput1, vtable slot 19: 3+16)
                    _dupOutput = ReadVtbl<DuplicateOutputDel>(pOutput, 19);
                    Hr(_dupOutput(pOutput, _pDevice, out _pDup), "DuplicateOutput");

                    // 6) Cache duplication vtable delegates
                    _getDesc = ReadVtbl<GetDescDel>(_pDup, 7);           // slot 7
                    _acquireFrame = ReadVtbl<AcquireNextFrameDel>(_pDup, 8);  // slot 8
                    _releaseFrame = ReadVtbl<ReleaseFrameDel>(_pDup, 14);     // slot 14

                    // 7) Get dimensions
                    DXGI_OUTDUPL_DESC dd;
                    _getDesc(_pDup, out dd);
                    _lastW = (int)dd.W;
                    _lastH = (int)dd.H;

                    // 8) Allocate staging texture + frame buffer
                    CreateStagingTexture();

                    // 9) Allocate pre-allocated pixel buffer
                    int maxW = 0, maxH = 0;
                    foreach (var s in System.Windows.Forms.Screen.AllScreens)
                    {
                        maxW = Math.Max(maxW, s.Bounds.Right + Math.Abs(Math.Min(0, s.Bounds.Left)));
                        maxH = Math.Max(maxH, s.Bounds.Bottom + Math.Abs(Math.Min(0, s.Bounds.Top)));
                    }
                    _bufW = Math.Max(maxW, _lastW + 64);
                    _bufH = Math.Max(maxH, _lastH + 64);
                    _frameBuf = new byte[_bufW * _bufH * 4];

                    _dxgiOk = true;

                    // Release adapter/output pointers (no longer needed after device created)
                    _release(pAdapter1);
                    _release(pOutput);
                }
                catch
                {
                    CleanupDxgi();
                    _dxgiOk = false;
                }
                finally { _initialized = true; }
            }
        }

        static void CreateStagingTexture()
        {
            if (_pStaging != IntPtr.Zero) { _release(_pStaging); _pStaging = IntPtr.Zero; }

            var td = new D3D11_TEX2D_DESC
            {
                W = (uint)_lastW, H = (uint)_lastH, Mip = 1, Arr = 1,
                Fmt = FMT_B8G8R8A8,
                Samp = new DXGI_SAMPLE_DESC { C = 1 },
                Usage = STAGING, CPU = CPU_READ
            };
            IntPtr pStg;
            int hr = _createTex2D(_pDevice, ref td, IntPtr.Zero, out pStg);
            if (hr == S_OK)
            {
                _pStaging = pStg;
            }
        }

        static void CleanupDxgi()
        {
            if (_pStaging != IntPtr.Zero) { _release(_pStaging); _pStaging = IntPtr.Zero; }
            if (_pDup != IntPtr.Zero) { _release(_pDup); _pDup = IntPtr.Zero; }
            if (_pContext != IntPtr.Zero) { _release(_pContext); _pContext = IntPtr.Zero; }
            if (_pDevice != IntPtr.Zero) { _release(_pDevice); _pDevice = IntPtr.Zero; }
            if (_pFactory != IntPtr.Zero) { _release(_pFactory); _pFactory = IntPtr.Zero; }
            _dxgiOk = false;
            _initialized = false;
        }

        // ==================== PNG encoder (no GDI+ Bitmap dependency) ====================

        // Minimal PNG writer: writes raw BGRA pixels to a PNG file
        static void WritePng(string filePath, byte[] pixels, int w, int h, int stride)
        {
            // Convert BGRA → RGBA and flip rows (PNG stores top-to-bottom, DXGI is top-to-bottom too)
            // Both BGRA and RGBA are bottom-up? No. DXGI: top-left origin. PNG: top-left origin.
            // But Format32bppArgb in .NET is actually BGRA byte order.
            // DXGI B8G8R8A8 is also BGRA. So byte order matches.

            // Just use GDI+ for simplicity (PNG encoder is complex to write from scratch)
            // But we avoid per-call Bitmap allocation by just creating one Bitmap here
            using (var bmp = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
            {
                var bd = bmp.LockBits(
                    new System.Drawing.Rectangle(0, 0, w, h),
                    System.Drawing.Imaging.ImageLockMode.WriteOnly,
                    System.Drawing.Imaging.PixelFormat.Format32bppArgb);

                int copyBytes = Math.Min(stride, bd.Stride);
                for (int y = 0; y < h; y++)
                {
                    IntPtr dst = bd.Scan0 + y * bd.Stride;
                    int srcOff = y * stride;
                    Marshal.Copy(pixels, srcOff, dst, copyBytes);
                }
                bmp.UnlockBits(bd);
                bmp.Save(filePath, System.Drawing.Imaging.ImageFormat.Png);
            }
        }

        // ==================== Public DXGI Capture ====================

        public static void DxgiToFile(string filePath)
        {
            lock (_lock)
            {
                if (!_initialized) InitDxgi();
                if (!_dxgiOk) throw new Exception("DXGI init failed");
            }

            // Check resolution change (rebuild staging if needed)
            DXGI_OUTDUPL_DESC dd;
            _getDesc(_pDup, out dd);
            int w = (int)dd.W, h = (int)dd.H;
            if (w != _lastW || h != _lastH)
            {
                _lastW = w; _lastH = h;
                CreateStagingTexture();
            }

            // Acquire frame (non-blocking poll, max 10 spins)
            IntPtr pRes = IntPtr.Zero; DXGI_OUTDUPL_FRAME_INFO fi; bool gotFrame = false;
            for (int i = 0; i < 10; i++)
            {
                int hr = _acquireFrame(_pDup, 0, out fi, out pRes);
                if (hr == S_OK) { gotFrame = true; break; }
                if (hr == W_TIMEOUT) { Thread.Sleep(1); continue; }
                if (hr == ACCESS_LOST) { CleanupDxgi(); throw new Exception("DXGI access lost (display mode change)"); }
                if (pRes != IntPtr.Zero) { _releaseFrame(_pDup); _release(pRes); pRes = IntPtr.Zero; }
                Hr(hr, "AcquireNextFrame");
            }
            if (!gotFrame) throw new Exception("AcquireNextFrame timed out");

            // Copy to staging
            _copyResource(_pContext, _pStaging, pRes);

            // Map + copy to pre-allocated buffer
            D3D11_MAPPED_SUBRESOURCE mr;
            Hr(_map(_pContext, _pStaging, 0, MAP_READ, 0, out mr), "Map");
            try
            {
                int srcStride = (int)mr.RowPitch;
                int rowBytes = w * 4;

                if (srcStride == rowBytes)
                {
                    // Fast path: single copy
                    Marshal.Copy(mr.pData, _frameBuf, 0, rowBytes * h);
                }
                else
                {
                    // Row-by-row copy
                    for (int y = 0; y < h; y++)
                    {
                        IntPtr src = mr.pData + y * srcStride;
                        Marshal.Copy(src, _frameBuf, y * rowBytes, rowBytes);
                    }
                }

                WritePng(filePath, _frameBuf, w, h, rowBytes);
            }
            finally { _unmap(_pContext, _pStaging, 0); }

            _releaseFrame(_pDup);
            if (pRes != IntPtr.Zero) _release(pRes);
        }

        // ==================== GDI Fallback (cached canvas) ====================

        public static void GdiToFile(string filePath)
        {
            var scr = System.Windows.Forms.Screen.AllScreens;
            int l = 0, t = 0, r = 0, b = 0;
            foreach (var s in scr)
            {
                l = Math.Min(l, s.Bounds.Left); t = Math.Min(t, s.Bounds.Top);
                r = Math.Max(r, s.Bounds.Right); b = Math.Max(b, s.Bounds.Bottom);
            }
            int w = r - l, h = b - t;

            // Reuse canvas if size unchanged
            if (_gdiCanvas == null || w != _gdiW || h != _gdiH)
            {
            if (_gdiGraphics != null) { _gdiGraphics.Dispose(); _gdiGraphics = null; }
            if (_gdiCanvas != null) { _gdiCanvas.Dispose(); _gdiCanvas = null; }
                _gdiCanvas = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
                _gdiGraphics = System.Drawing.Graphics.FromImage(_gdiCanvas);
                _gdiW = w; _gdiH = h;
            }

            _gdiGraphics.CopyFromScreen(l, t, 0, 0, new System.Drawing.Size(w, h));
            _gdiCanvas.Save(filePath, System.Drawing.Imaging.ImageFormat.Png);
        }

        // ==================== Public release ====================

        public static void Shutdown()
        {
            lock (_lock)
            {
                CleanupDxgi();
                if (_gdiGraphics != null) { _gdiGraphics.Dispose(); _gdiGraphics = null; }
                if (_gdiCanvas != null) { _gdiCanvas.Dispose(); _gdiCanvas = null; }
                _frameBuf = null;
                _enumAdapters1 = null; _enumOutputs = null; _dupOutput = null;
                _acquireFrame = null; _releaseFrame = null; _getDesc = null;
                _createTex2D = null; _map = null; _unmap = null; _copyResource = null;
                _qi = null; _addRef = null; _release = null;
            }
        }
    }
}
