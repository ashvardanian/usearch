import os
import sys
import subprocess
from setuptools import setup, Extension

from pybind11.setup_helpers import Pybind11Extension

compile_args = []
link_args = []
macros_args = []
include_dirs = ["include"]


def get_bool_env(name: str, preference: bool) -> bool:
    return os.environ.get(name, "1" if preference else "0") == "1"


def get_bool_env_w_name(name: str, preference: bool) -> tuple:
    return name, "1" if get_bool_env(name, preference) else "0"


def call_system(*args) -> str:
    return subprocess.check_output(args).strip().decode()


# Check the environment variables
is_linux: bool = sys.platform == "linux"
is_macos: bool = sys.platform == "darwin"
is_windows: bool = sys.platform == "win32"


is_gcc = False
if is_linux:
    cxx = os.environ.get("CXX")
    if cxx:
        try:
            command = "where" if os.name == "nt" else "which"
            full_path = subprocess.check_output([command, cxx], text=True).strip()
            compiler_name = os.path.basename(full_path)
            is_gcc = ("g++" in compiler_name) and ("clang++" not in compiler_name)
        except subprocess.CalledProcessError:
            pass


prefer_simsimd: bool = is_linux or is_macos
prefer_fp16lib: bool = True
prefer_openmp: bool = is_linux and is_gcc
prefer_stringzilla: bool = True

use_simsimd: bool = get_bool_env("USEARCH_USE_SIMSIMD", prefer_simsimd)
use_fp16lib: bool = get_bool_env("USEARCH_USE_FP16LIB", prefer_fp16lib)
use_openmp: bool = get_bool_env("USEARCH_USE_OPENMP", prefer_openmp)
use_stringzilla: bool = get_bool_env("USEARCH_USE_STRINGZILLA", prefer_stringzilla)

# Common arguments for all platforms
macros_args.append(("USEARCH_USE_OPENMP", "1" if use_openmp else "0"))
macros_args.append(("USEARCH_USE_SIMSIMD", "1" if use_simsimd else "0"))
macros_args.append(("USEARCH_USE_FP16LIB", "1" if use_fp16lib else "0"))
macros_args.append(("USEARCH_USE_STRINGZILLA", "1" if use_stringzilla else "0"))

if use_simsimd:
    include_dirs.append("simsimd/include")
if use_fp16lib:
    include_dirs.append("fp16/include")
if use_stringzilla:
    include_dirs.append("stringzilla/include")

if is_linux:
    # compile_args.append("-std=c++17")
    compile_args.append("-O3")  # Maximize performance
    compile_args.append("-ffast-math")  # Maximize floating-point performance
    compile_args.append("-Wno-unknown-pragmas")
    compile_args.append("-fdiagnostics-color=always")

    # Simplify debugging, but the normal `-g` may make builds much longer!
    compile_args.append("-g1")

    if use_openmp:
        compile_args.append("-fopenmp")
        link_args.append("-lgomp")

    if use_simsimd:
        macros_args.extend(
            [
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX512", True),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_SVE", True),
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX2", True),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_NEON", True),
            ]
        )

if is_macos:
    # MacOS 10.15 or higher is needed for `aligned_alloc` support.
    # https://github.com/unum-cloud/usearch/actions/runs/4975434891/jobs/8902603392
    compile_args.append("-mmacosx-version-min=10.15")
    # compile_args.append("-std=c++17")
    compile_args.append("-O3")  # Maximize performance
    compile_args.append("-ffast-math")  # Maximize floating-point performance
    compile_args.append("-fcolor-diagnostics")
    compile_args.append("-Wno-unknown-pragmas")

    # Simplify debugging, but the normal `-g` may make builds much longer!
    compile_args.append("-g1")

    # For Postgres we need to link
    pg_libdir = call_system("pg_config", "--libdir")
    link_args.append(f"-L{pg_libdir}")
    # Linking against all of those libraries is hard
    # link_args.extend(call_system("pg_config", "--libs").split())
    include_dirs.extend(call_system("pg_config", "--includedir-server").split())
    compile_args.append("-bundle -flat_namespace -undefined suppress")

    # Linking OpenMP requires additional preparation in CIBuildWheel.
    # We must install `brew install llvm` ahead of time.
    # import subprocess as cli
    # llvm_base = cli.check_output(["brew", "--prefix", "llvm"]).strip().decode("utf-8")
    # if len(llvm_base):
    #     compile_args.append(f"-I{llvm_base}/include")
    #     compile_args.append("-Xpreprocessor -fopenmp")
    #     link_args.append(f"-L{llvm_base}/lib")
    #     link_args.append("-lomp")
    #     macros_args.append(("USEARCH_USE_OPENMP", "1"))

    if use_simsimd:
        macros_args.extend(
            [
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX512", False),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_SVE", False),
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX2", True),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_NEON", True),
            ]
        )

if is_windows:
    compile_args.append("/std:c++17")
    compile_args.append("/O2")
    compile_args.append("/fp:fast")  # Enable fast math for MSVC
    compile_args.append("/W1")  # Reduce warnings verbosity

    # We don't actually want to use any SimSIMD stuff,
    # as GCC attributes aren't compatible with MSVC
    if use_simsimd:
        macros_args.extend(
            [
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX512", False),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_SVE", False),
                get_bool_env_w_name("SIMSIMD_TARGET_X86_AVX2", False),
                get_bool_env_w_name("SIMSIMD_TARGET_ARM_NEON", False),
            ]
        )

print("macros_args", macros_args)

ext_modules = [
    Pybind11Extension(
        "usearch.compiled",
        ["python/lib.cpp"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
        define_macros=macros_args,
        include_dirs=include_dirs,
    ),
    Extension(
        "usearch_sqlite",
        ["python/lib_sqlite.cpp"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
        define_macros=macros_args,
        include_dirs=include_dirs,
    ),
    Extension(
        "usearch_postgres",
        ["python/lib_postgres.c"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
        define_macros=macros_args,
        include_dirs=include_dirs,
    ),
]

__version__ = open("VERSION", "r").read().strip()
__lib_name__ = "usearch"

this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md")) as f:
    long_description = f.read()


setup(
    name=__lib_name__,
    version=__version__,
    packages=["usearch"],
    package_dir={"usearch": "python/usearch"},
    description="Smaller & Faster Single-File Vector Search Engine from Unum",
    author="Ash Vardanian",
    author_email="info@unum.cloud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: C++",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Java",
        "Programming Language :: JavaScript",
        "Programming Language :: Objective C",
        "Programming Language :: Rust",
        "Programming Language :: Other",
        "Operating System :: MacOS",
        "Operating System :: Unix",
        "Operating System :: Microsoft :: Windows",
        "Topic :: System :: Clustering",
        "Topic :: Database :: Database Engines/Servers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    ext_modules=ext_modules,
    install_requires=["numpy"],
)
