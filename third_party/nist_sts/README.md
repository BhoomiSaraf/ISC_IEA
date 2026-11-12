# Official NIST Statistical Test Suite (STS) 2.1.2

Third-party code. Everything under `src_pristine/` and `build_linux/` is NIST's
distribution, unmodified, apart from the objects and the `assess` binary that the
official makefile produced in `build_linux/`.

| item | value |
|---|---|
| source page | https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software |
| archive | https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip (page date 2014-07-09) |
| archive SHA-256 | `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157` (43,915,127 bytes) |
| documentation | NIST SP 800-22 Rev. 1a, https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-22r1a.pdf |
| documentation SHA-256 | `38aba1b34a7fa52c440790d6e0cabf498e4b525177b3b6cebb399ab8ccf031d2` |

Layout:

* `download/`: the archive, the PDF, the HTTP response headers, and the PDF text extracted with pypdf.
* `src_pristine/`: `unzip` of the archive (reference copy, never built in).
* `build_linux/`: copy of the pristine tree, built in WSL Ubuntu 24.04 (gcc 13.3.0, GNU make 4.3)
  with the official makefile: `make`. See `build_linux/build.log`.

The archive contains only C sources, headers, the makefile, template files, sample
data and a directory-creation shell script; it has no binaries. The shell script was
not executed: the harness creates the directories itself.

Known portability issue (from the sources, confirmed by running): the built-in
generators use `typedef unsigned long ULONG` as a 32-bit word (`include/config.h`), which
is 64 bits on x86_64 Linux. The built-in "G using SHA-1" generator therefore does not
produce the reference G-SHA-1 sequence on this build. Only input-file mode is used for
the ISC evaluation, and it is unaffected.

Rebuild:

```bash
cd third_party/nist_sts
unzip -q download/sts-2_1_2.zip -d src_pristine
cp -r src_pristine/sts-2.1.2/sts-2.1.2/. build_linux/
wsl -d Ubuntu-24.04 --cd "$(wslpath -a build_linux)" -- make
```
