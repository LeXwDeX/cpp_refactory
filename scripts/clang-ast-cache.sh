#!/usr/bin/env bash
# clang-ast-cache.sh — Manage the on-disk libclang TU cache.
#
# 子命令：
#   stats              显示磁盘缓存使用情况（数量、总大小、最大文件 TOP）
#   list               列出缓存中的所有 TU 及其源文件路径
#   clean              清空所有缓存
#   clean --older N    清理 N 天前的缓存
#
# 缓存目录：$CPP_REFACTORY_CACHE_DIR/tu/  默认 ~/.cache/clang-ast-mcp/tu/

set -uo pipefail

CACHE_DIR="${CPP_REFACTORY_CACHE_DIR:-$HOME/.cache/clang-ast-mcp}/tu"

cmd="${1:-stats}"

case "$cmd" in
    stats)
        if [[ ! -d "$CACHE_DIR" ]]; then
            echo "Cache dir does not exist: $CACHE_DIR"
            exit 0
        fi
        tu_count=$(find "$CACHE_DIR" -maxdepth 1 -name '*.tu' -type f 2>/dev/null | wc -l)
        total_size=$(du -sb "$CACHE_DIR" 2>/dev/null | cut -f1)
        total_mb=$(awk "BEGIN { printf \"%.2f\", ${total_size:-0}/1048576 }")
        echo "Cache dir : $CACHE_DIR"
        echo "TU files  : $tu_count"
        echo "Total size: ${total_mb} MB"
        echo ""
        echo "Top 10 largest TUs:"
        find "$CACHE_DIR" -maxdepth 1 -name '*.tu' -type f -printf '%s\t%f\n' 2>/dev/null \
            | sort -rn | head -10 \
            | awk '{ printf "  %.2f MB  %s\n", $1/1048576, $2 }'
        ;;
    list)
        if [[ ! -d "$CACHE_DIR" ]]; then
            echo "Cache dir does not exist: $CACHE_DIR"
            exit 0
        fi
        printf "%-12s  %-10s  %s\n" "AGE" "SIZE" "SOURCE"
        for meta in "$CACHE_DIR"/*.meta.json; do
            [[ -f "$meta" ]] || continue
            src=$(python3 -c "import json,sys; print(json.load(open('$meta')).get('source_path','?'))" 2>/dev/null)
            tu="${meta%.meta.json}.tu"
            if [[ -f "$tu" ]]; then
                size=$(du -h "$tu" | cut -f1)
                age=$(stat -c %y "$tu" | cut -d. -f1)
                printf "%-12s  %-10s  %s\n" "${age#* }" "$size" "$src"
            fi
        done
        ;;
    clean)
        if [[ ! -d "$CACHE_DIR" ]]; then
            echo "Cache dir does not exist; nothing to clean."
            exit 0
        fi
        if [[ "${2:-}" == "--older" && -n "${3:-}" ]]; then
            days="$3"
            count=$(find "$CACHE_DIR" -maxdepth 1 \( -name '*.tu' -o -name '*.meta.json' \) -mtime +"$days" 2>/dev/null | wc -l)
            find "$CACHE_DIR" -maxdepth 1 \( -name '*.tu' -o -name '*.meta.json' \) -mtime +"$days" -delete 2>/dev/null
            echo "Removed $count files older than $days days from $CACHE_DIR"
        else
            count=$(find "$CACHE_DIR" -maxdepth 1 \( -name '*.tu' -o -name '*.meta.json' \) 2>/dev/null | wc -l)
            find "$CACHE_DIR" -maxdepth 1 \( -name '*.tu' -o -name '*.meta.json' \) -delete 2>/dev/null
            echo "Removed $count files from $CACHE_DIR"
        fi
        ;;
    -h|--help|help)
        sed -n '1,12p' "$0" | sed 's/^# \?//'
        ;;
    *)
        echo "Unknown subcommand: $cmd" >&2
        echo "Run: $0 help" >&2
        exit 1
        ;;
esac
