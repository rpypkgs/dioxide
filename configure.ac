AC_INIT(dioxide, [0.1], [cds@corbinsimpson.com])

AM_INIT_AUTOMAKE([-Wall -Werror foreign])

AC_PROG_CC

AC_CHECK_LIB(m, sin)
AC_CHECK_LIB(dl, dlopen)

PKG_CHECK_MODULES(ALSA, alsa)

AM_PATH_SDL([1.2.0])

AC_CONFIG_FILES([
    Makefile
])
AC_OUTPUT
