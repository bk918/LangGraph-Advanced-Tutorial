# 맥북에서 unsloth 설치 시 주의사항

❯ uv add unsloth datasets
Resolved 417 packages in 956ms
warning: `pyobjc-core==12.0` is yanked (reason: "python_requires erroneously claims support for Python 3.9")
warning: `pyobjc-core==12.0` is yanked (reason: "python_requires erroneously claims support for Python 3.9")
error: Distribution `bitsandbytes==0.48.2 @ registry+https://pypi.org/simple` can't be installed because it doesn't have a source distribution or wheel for the current platform

---

hint: You're on macOS (`macosx_26_0_arm64`), but `bitsandbytes` (v0.48.2) only has wheels for the following platforms: `manylinux_2_24_aarch64`, `manylinux_2_24_x86_64`, `win_amd64`; consider adding "sys_platform == 'darwin' and platform_machine == 'arm64'" to `tool.uv.required-environments` to ensure uv resolves to a version with compatible wheels
