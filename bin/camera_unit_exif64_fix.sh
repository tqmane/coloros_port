#!/usr/bin/env bash
set -euo pipefail

# Preserve/restore the modern Camera Unit SDK around the legacy Camera 6 fix.
# This fixes the EXIF flag ABI at the framework boundary without modifying
# OplusCamera.apk.
#
# Usage:
#   camera_unit_exif64_fix.sh preserve <images-root> <backup-dir> [checker]
#   camera_unit_exif64_fix.sh restore  <images-root> <backup-dir> [checker]

usage() {
    cat >&2 <<'EOF'
Usage:
  camera_unit_exif64_fix.sh preserve <images-root> <backup-dir> [checker]
  camera_unit_exif64_fix.sh restore  <images-root> <backup-dir> [checker]
EOF
    exit 2
}

[[ $# -ge 3 ]] || usage
mode=$1
images_root=$2
backup_dir=$3
checker=${4:-"$(cd "$(dirname "$0")" && pwd)/check_camera_unit_exif_abi.py"}

framework_dir="$images_root/my_product/product_overlay/framework"
sdk="$framework_dir/com.oplus.camera.unit.sdk.jar"
adapter="$framework_dir/com.oplus.camera.unit.sdk.adapter.jar"

check_sdk() {
    local candidate=$1
    if [[ ! -f "$checker" ]]; then
        echo "[camera-exif64] checker missing: $checker" >&2
        return 1
    fi
    if ! python3 "$checker" "$candidate" --require-exif64-dual; then
        echo "[camera-exif64] Camera Unit SDK is not EXIF64 dual-compatible: $candidate" >&2
        echo "[camera-exif64] Refusing to build a ROM that would reintroduce long[] -> int[] ABI skew." >&2
        return 1
    fi
}

case "$mode" in
    preserve)
        [[ -f "$sdk" ]] || {
            echo "[camera-exif64] missing port-ROM SDK: $sdk" >&2
            exit 1
        }
        [[ -f "$adapter" ]] || {
            echo "[camera-exif64] missing port-ROM adapter: $adapter" >&2
            exit 1
        }

        check_sdk "$sdk"
        rm -rf "$backup_dir"
        mkdir -p "$backup_dir"
        cp -f "$sdk" "$backup_dir/com.oplus.camera.unit.sdk.jar"
        cp -f "$adapter" "$backup_dir/com.oplus.camera.unit.sdk.adapter.jar"
        (
            cd "$backup_dir"
            sha256sum \
                com.oplus.camera.unit.sdk.jar \
                com.oplus.camera.unit.sdk.adapter.jar \
                > SHA256SUMS
        )
        echo "[camera-exif64] preserved modern Camera Unit SDK pair from PORTROM"
        ;;

    restore)
        saved_sdk="$backup_dir/com.oplus.camera.unit.sdk.jar"
        saved_adapter="$backup_dir/com.oplus.camera.unit.sdk.adapter.jar"
        [[ -f "$saved_sdk" && -f "$saved_adapter" ]] || {
            echo "[camera-exif64] preserved SDK pair is incomplete: $backup_dir" >&2
            exit 1
        }
        (cd "$backup_dir" && sha256sum -c SHA256SUMS)
        check_sdk "$saved_sdk"

        mkdir -p "$framework_dir"
        cp -f "$saved_sdk" "$sdk"
        cp -f "$saved_adapter" "$adapter"

        # camera6.0-fix_cos.zip carries preopt files generated for its legacy
        # int32 Camera Unit SDK. They must never survive after the JAR pair is
        # restored, otherwise ART can resolve against stale code.
        rm -f \
            "$framework_dir/oat/arm64/com.oplus.camera.unit.sdk.odex" \
            "$framework_dir/oat/arm64/com.oplus.camera.unit.sdk.vdex" \
            "$framework_dir/oat/arm64/com.oplus.camera.unit.sdk.adapter.odex" \
            "$framework_dir/oat/arm64/com.oplus.camera.unit.sdk.adapter.vdex"

        # The camera APK itself is intentionally left byte-for-byte untouched.
        # Only discard its stale preopt so it is resolved/compiled against the
        # restored framework pair on the target ROM.
        rm -rf "$images_root/my_product/app/OplusCamera/oat"

        check_sdk "$sdk"
        echo "[camera-exif64] restored modern EXIF64 Camera Unit SDK pair"
        ;;

    *)
        usage
        ;;
esac
