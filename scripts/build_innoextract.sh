#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
commit=6e9e34ed0876014fdb46e684103ef8c3605e382e
checksum=4d885b27e452dcb137a9d97736b19478447f172bcfed1aa98d80138e9a4c08ae
archive="$root/tools/innoextract-source.tar.gz"
source_dir="$root/tools/innoextract-$commit"
build="$root/tools/inno-build"
sysroot="$root/tools/sysroot/usr"

mkdir -p "$root/tools"
if [ ! -f "$archive" ]; then
  curl -fL "https://codeload.github.com/dscharrer/innoextract/tar.gz/$commit" -o "$archive"
fi
printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
tar -xf "$archive" -C "$root/tools"

python3 - "$source_dir/CMakeLists.txt" <<'PY'
import sys
from pathlib import Path

cmake = Path(sys.argv[1])
cmake.write_text(cmake.read_text().replace("\n\tdate_time\n\tsystem\n", "\n"))
PY

options=()
if [ -d "$sysroot/include/boost" ]; then
  options+=("-DBOOST_ROOT=$sysroot" "-DBoost_NO_SYSTEM_PATHS=ON" "-DCMAKE_PREFIX_PATH=$sysroot")
fi
cmake -S "$source_dir" -B "$build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_DEFAULT_CMP0167=OLD \
  -DBoost_NO_BOOST_CMAKE=ON -DUSE_LTO=OFF "${options[@]}"
cmake --build "$build" -j 4
"$build/innoextract" --version
