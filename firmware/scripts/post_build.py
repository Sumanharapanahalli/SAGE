# ==============================================================================
# PlatformIO post-build script — GuardianSense firmware
# Copies .elf/.bin/.hex artifacts to build_output/ after a successful build.
# Attached to the stm32l4_release environment via extra_scripts.
# ==============================================================================
import os
import shutil
from pathlib import Path

Import("env")  # noqa: F821 — PlatformIO injects this


def post_build_actions(source, target, env):  # noqa: ANN001
    build_dir = Path(env.subst("$BUILD_DIR"))
    project_dir = Path(env.subst("$PROJECT_DIR"))
    artifacts_dir = project_dir / "build_output"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Locate the ELF produced by the build
    elf_candidates = list(build_dir.glob("*.elf"))
    if not elf_candidates:
        print("[post_build] WARNING: no .elf found in BUILD_DIR — skipping artifact copy")
        return

    elf_path = elf_candidates[0]
    print(f"[post_build] ELF: {elf_path}")

    # Copy ELF
    shutil.copy2(elf_path, artifacts_dir / elf_path.name)

    # Copy or generate BIN
    bin_path = build_dir / (elf_path.stem + ".bin")
    if bin_path.exists():
        shutil.copy2(bin_path, artifacts_dir / bin_path.name)
        print(f"[post_build] BIN: {artifacts_dir / bin_path.name}")
    else:
        objcopy = env.subst("$OBJCOPY")
        output_bin = artifacts_dir / (elf_path.stem + ".bin")
        env.Execute(f"{objcopy} -O binary {elf_path} {output_bin}")
        print(f"[post_build] BIN generated: {output_bin}")

    # Generate HEX
    objcopy = env.subst("$OBJCOPY")
    output_hex = artifacts_dir / (elf_path.stem + ".hex")
    env.Execute(f"{objcopy} -O ihex {elf_path} {output_hex}")
    print(f"[post_build] HEX generated: {output_hex}")

    # Print size summary
    size_tool = env.subst("$SIZE")
    env.Execute(f"{size_tool} {elf_path}")

    print(f"[post_build] All artifacts written to: {artifacts_dir}")


env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", post_build_actions)
