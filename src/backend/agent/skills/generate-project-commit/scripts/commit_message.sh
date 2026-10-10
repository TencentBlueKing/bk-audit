#!/bin/sh
# 后端提交标题校验的唯一规则入口；只依赖 POSIX sh、awk 和 Git。
# validate/classify 接收 stdin 或 --message-file；hook 按暂存范围隔离前端。
# check-log/check-range 检查标题历史，不修改提交、索引或 message 文件。

set -eu

usage() {
    # 输出调用格式；参数错误由调用者以状态 2 退出。
    cat >&2 <<'EOF'
Usage: commit_message.sh validate|classify|hook [--allow-merge] [--message-file FILE]
       commit_message.sh check-log [-n COUNT]
       commit_message.sh check-range REVISION_RANGE
EOF
}

check_subjects() {
    # $1 输入模式（message/classify/history），$2 是否允许合并标题；输入为 stdin。
    # 返回 0 表示标题合法，1 表示标题非法；正文不作硬性要求。
    awk -v mode="$1" -v allow_merge="$2" '
        function classify(subject) {
            if (subject ~ /^(feat|fix|docs|style|refactor|perf|test|chore):[[:space:]]+[^[:space:]].*[[:space:]]#[0-9]+$/)
                return "Github Type"
            if (subject ~ /^(feat|fix|docs|style|refactor|perf|test|chore):[[:space:]]+[^[:space:]].*[[:space:]]--[^=[:space:]]+=[0-9]+$/)
                return "TAPD Type"
            if (allow_merge && subject ~ /^Merge([[:space:]]|$)/)
                return "Merge Type"
            return ""
        }
        mode == "history" || NR == 1 {
            subject = $0
            sub(/\r$/, "", subject)
            sub(/^[[:space:]]+/, "", subject)
            sub(/[[:space:]]+$/, "", subject)
            kind = classify(subject)
            if (!kind) {
                print "Invalid commit subject: " subject > "/dev/stderr"
                print "Expected type: summary #issue or type: summary --story=1234 (numeric TAPD tracker)." > "/dev/stderr"
                failed = 1
            } else if (mode == "classify") {
                print kind
            } else if (mode == "history") {
                print "[" NR "] " kind ": " subject
            }
        }
        END {
            if (NR == 0 && mode != "history") {
                print "Commit message is empty" > "/dev/stderr"
                failed = 1
            }
            exit failed ? 1 : 0
        }
    '
}

backend_hook_needed() {
    # 返回 0 需校验、1 仅有非后端改动、2 Git 检查失败。
    # 空暂存差异不能直接跳过，否则 amend/reword 会再次漏检。
    git_root=$(git rev-parse --show-toplevel) || return 2
    if git -C "$git_root" diff --cached --quiet -- src/backend; then
        if git -C "$git_root" diff --cached --quiet; then
            return 0
        else
            diff_status=$?
            [ "$diff_status" -eq 1 ] && return 1
            return 2
        fi
    else
        diff_status=$?
        [ "$diff_status" -eq 1 ] && return 0
        return 2
    fi
}

[ "$#" -gt 0 ] || { usage; exit 2; }
command=$1
shift
allow_merge=0
message_file=
limit=20
revision_range=

case "$command" in
    validate|classify|hook)
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --allow-merge) allow_merge=1; shift ;;
                --message-file)
                    [ "$#" -ge 2 ] || { usage; exit 2; }
                    message_file=$2
                    shift 2
                    ;;
                *) usage; exit 2 ;;
            esac
        done
        ;;
    check-log)
        if [ "$#" -gt 0 ]; then
            [ "$#" -eq 2 ] || { usage; exit 2; }
            [ "$1" = -n ] || [ "$1" = --limit ] || { usage; exit 2; }
            limit=$2
        fi
        case "$limit" in ''|*[!0-9]*) usage; exit 2 ;; esac
        [ "$limit" -gt 0 ] || { usage; exit 2; }
        ;;
    check-range)
        [ "$#" -eq 1 ] || { usage; exit 2; }
        revision_range=$1
        case "$revision_range" in ''|-*) usage; exit 2 ;; esac
        ;;
    *) usage; exit 2 ;;
esac

case "$command" in
    hook)
        [ -n "$message_file" ] && [ -r "$message_file" ] || { usage; exit 2; }
        if backend_hook_needed; then
            allow_merge=1
        else
            scope_status=$?
            if [ "$scope_status" -eq 1 ]; then
                echo "No backend changes; backend commit-message check skipped"
                exit 0
            fi
            echo "Cannot inspect staged backend changes" >&2
            exit 2
        fi
        ;;
    check-log|check-range)
        # 先检查 Git 的退出码，再交给 awk，避免管道掩盖无效 revision。
        history_file=$(mktemp "${TMPDIR:-/tmp}/bk-audit-commit-log.XXXXXX")
        trap 'rm -f "$history_file"' 0 HUP INT TERM
        if [ "$command" = check-log ]; then
            git log -n "$limit" --format=%s > "$history_file"
        else
            git log --format=%s "$revision_range" -- > "$history_file"
        fi
        check_subjects history 1 < "$history_file"
        exit 0
        ;;
esac

input_mode=message
[ "$command" != classify ] || input_mode=classify
if [ -n "$message_file" ]; then
    [ -r "$message_file" ] || { echo "Cannot read commit message file" >&2; exit 2; }
    check_subjects "$input_mode" "$allow_merge" < "$message_file"
else
    check_subjects "$input_mode" "$allow_merge"
fi
[ "$command" = classify ] || echo "Valid commit message"
