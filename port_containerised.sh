#!/bin/bash

invocation_dir=$(pwd -P)
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
source "${script_dir}/functions.sh"

resolve_host_path() {
    local value="${1:-}"
    if [[ -z "$value" || "$value" =~ ^https?:// || "$value" = /* ]]; then
        printf '%s\n' "$value"
    else
        printf '%s/%s\n' "$invocation_dir" "$value"
    fi
}

check distrobox
blue "Checking if container exists"
if distrobox list 2>/dev/null | grep -q "coloros_port_container"; then
    blue "Container exists"
else
    blue "Container does not exist. Creating..."
    distrobox assemble create --file "${script_dir}/distrobox.ini" || exit 1
fi

distrobox enter coloros_port_container -- \
    sudo "${script_dir}/port.sh" \
    "$(resolve_host_path "${1:-}")" \
    "$(resolve_host_path "${2:-}")" \
    "$(resolve_host_path "${3:-}")" \
    "${4:-}"
