from rpython.rtyper.lltypesystem import lltype, rffi
from rpython.rtyper.tool import rffi_platform
from rpython.translator.tool.cbuild import ExternalCompilationInfo


eci = ExternalCompilationInfo(includes=["alsa/asoundlib.h"])
eci = eci.merge(ExternalCompilationInfo.from_pkg_config("alsa"))

seq_t = rffi.COpaquePtr("snd_seq_t")
seq_tp = lltype.FixedSizeArray(seq_t, 1)

constants = ("SEQ_OPEN_INPUT", "SEQ_NONBLOCK", "SEQ_PORT_CAP_WRITE",
             "SEQ_PORT_CAP_SUBS_WRITE", "SEQ_PORT_TYPE_MIDI_GENERIC")


class CConfig:
    _compilation_info_ = eci

for c in constants:
    setattr(CConfig, c, rffi_platform.ConstantInteger("SND_" + c))

globals().update(rffi_platform.configure(CConfig))

def ext(n, *args):
    return rffi.llexternal("snd_" + n, *args, compilation_info=eci)

strerror = ext("strerror", [rffi.INT], rffi.CCHARP)
seq_open = ext("seq_open", [seq_tp, rffi.CCHARP, rffi.INT, rffi.INT],
               rffi.INT)
seq_close = ext("seq_close", [seq_t], lltype.Void)
seq_set_client_name = ext("seq_set_client_name", [seq_t, rffi.CCHARP],
                          rffi.INT)
seq_create_simple_port = ext("seq_create_simple_port",
                             [seq_t, rffi.CCHARP, rffi.UINT, rffi.UINT],
                             rffi.INT)
