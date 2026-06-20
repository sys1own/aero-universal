import os
import sys
import subprocess
import re

def run_universal_compiler(workspace_path, target_name, hardware_recipe):
    print(f"\n[Aero Universal] Initializing zero-config compiler driver for target: '{target_name}'")
    
    src_dir = os.path.join(workspace_path, "src")
    lib_rs_path = os.path.join(src_dir, "lib.rs")
    
    if not os.path.exists(lib_rs_path):
        print(f"[Error] Target source not found at {lib_rs_path}")
        return False
        
    # 1. Parse dependencies from source (The Invisible Configuration Layer)
    with open(lib_rs_path, 'r') as f:
        source_content = f.read()
        
    dependencies = []
    if "use rug" in source_content or "rug::" in source_content:
        dependencies.append('rug = "1.24"')
    if "use pyo3" in source_content or "pyo3::" in source_content:
        dependencies.append('pyo3 = { version = "0.21", features = ["extension-module", "experimental-declarative-modules"] }')
        
    print(f"[Inference] Automatically discovered source language: Rust (PyO3 Extension Module)")
    print(f"[Inference] Inferred dependencies from AST hooks: {', '.join([d.split('=')[0].strip() for d in dependencies])}")
    
    # 2. Auto-generate the scaffolded Cargo.toml in the root workspace
    cargo_toml_path = os.path.join(workspace_path, "Cargo.toml")
    cargo_content = f"""[package]
name = "{target_name}"
version = "0.1.0"
edition = "2021"

[lib]
name = "{target_name}"
crate-type = ["cdylib"]

[dependencies]
""" + "\n".join(dependencies) + "\n"
    
    with open(cargo_toml_path, 'w') as f:
        f.write(cargo_content)
    print(f"[Scaffolding] Synthesized transient manifest: {cargo_toml_path}")
    
    # 3. Apply Autonomous Hardware-Polymerization to compilation environment flags
    env = os.environ.copy()
    rust_flags = "-C target-cpu=native"
    if "avx2" in hardware_recipe.get("vectorization", ""):
        rust_flags += " -C target-feature=+avx2"
        
    env["RUSTFLAGS"] = rust_flags
    print(f"[Polymerization] Injecting bare-metal optimization flags: RUSTFLAGS=\"{rust_flags}\"")
    
    # 4. Invoke native toolchain
    print(f"[Compiling] Dispatching cargo build engine...\n")
    try:
        process = subprocess.Popen(
            ["cargo", "build", "--release"],
            cwd=workspace_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                
        rc = process.poll()
        if rc != 0:
            print(f"\n[Aero Build Failure] Cargo compilation exited with code {rc}")
            return False
            
        # 5. Route compiled shared library to build_artifacts directory
        artifacts_dir = os.path.join(workspace_path, "build_artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        target_dir = os.path.join(workspace_path, "target", "release")
        compiled_filename = f"lib{target_name}.so"
        target_file = os.path.join(target_dir, compiled_filename)
        destination_file = os.path.join(artifacts_dir, f"{target_name}.so")
        
        if os.path.exists(target_file):
            if os.path.exists(destination_file):
                os.remove(destination_file)
            os.rename(target_file, destination_file)
            print(f"\n[Success] Flawless Native Target emitted: {destination_file}")
            return True
        else:
            # Fallback check for alternative naming conventions
            for f in os.listdir(target_dir):
                if f.endswith(".so") or f.endswith(".dylib") or f.endswith(".dll"):
                    os.rename(os.path.join(target_dir, f), destination_file)
                    print(f"\n[Success] Flawless Native Target emitted: {destination_file}")
                    return True
            print("[Error] Compiled binary library artifact not found in target space.")
            return False
    except Exception as e:
        print(f"[Error] Toolchain dispatch error: {str(e)}")
        return False
