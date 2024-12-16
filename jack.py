from rpython.rtyper.lltypesystem import lltype, rffi
from rpython.rtyper.tool import rffi_platform
from rpython.translator.tool.cbuild import ExternalCompilationInfo


eci = ExternalCompilationInfo(includes=["jack/jack.h", "jack/midiport.h"])
eci = eci.merge(ExternalCompilationInfo.from_pkg_config("jack"))

client_t = rffi.COpaquePtr("jack_client_t")
port_t = rffi.COpaquePtr("jack_port_t")

Constants = ("ServerFailed", "ServerStarted", "NameNotUnique", "PortIsInput",
             "PortIsOutput", "PortIsPhysical")

CONSTANTS = "DEFAULT_AUDIO_TYPE", "DEFAULT_MIDI_TYPE"


def cb(n, *args):
    n += "Callback"
    globals()[n] = lltype.Ptr(lltype.FuncType(*args))

cb("BufferSize", [rffi.UINT, rffi.VOIDP], rffi.INT)
cb("Process", [rffi.UINT, rffi.VOIDP], rffi.INT)
cb("SampleRate", [rffi.UINT, rffi.VOIDP], rffi.INT)
cb("Shutdown", [rffi.VOIDP], lltype.Void)


class CConfig:
    _compilation_info_ = eci

for c in Constants:
    setattr(CConfig, c, rffi_platform.ConstantInteger("Jack" + c))
for c in CONSTANTS:
    setattr(CConfig, c, rffi_platform.DefinedConstantString("JACK_" + c))

globals().update(rffi_platform.configure(CConfig))

def ext(n, *args):
    globals()[n] = rffi.llexternal("jack_" + n, *args, compilation_info=eci)


ext("client_open", [rffi.CCHARP, rffi.INT, rffi.VOIDP], client_t)
ext("get_client_name", [client_t], rffi.CCHARP)
ext("get_sample_rate", [client_t], rffi.UINT)
ext("get_buffer_size", [client_t], rffi.UINT)
ext("client_close", [client_t], rffi.INT)
ext("activate", [client_t], rffi.INT)
ext("deactivate", [client_t], rffi.INT)
ext("set_process_callback", [client_t, ProcessCallback, rffi.VOIDP], rffi.INT)
ext("set_buffer_size_callback", [client_t, BufferSizeCallback, rffi.VOIDP], rffi.INT)
ext("set_sample_rate_callback", [client_t, SampleRateCallback, rffi.VOIDP], rffi.INT)
ext("on_shutdown", [ShutdownCallback, rffi.VOIDP], lltype.Void)
ext("port_register", [client_t, rffi.CCHARP, rffi.CCHARP, rffi.ULONG,
                      rffi.ULONG], port_t)
ext("port_unregister", [client_t, port_t], rffi.INT)
