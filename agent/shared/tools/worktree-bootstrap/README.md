# Worktree 本地材料初始化

解决 Agent 直接执行 git worktree add 后遗漏本地材料的问题，不依赖 Agent 记得补链接。
第一版只处理后端 src/backend/debug/ 下**明确批准的专题目录**，不自动共享整个 debug。

## 边界与设计

- 默认不启用。只读代码或 checkout 不会安装 hook；需本人审阅代码、确认白名单后一次性安装。
- 源码随 Git；本机配置、程序快照和 hook 存在仓库的 Git 公共目录，不提交个人路径，不改全局配置。
- hook 执行已审阅程序的**安装快照**，不执行新分支携带的代码，旧分支没有该脚本也可初始化。
- 根/后端 AGENTS.md 必须来自当前 checkout 且被跟踪；缺失只报告，不复制主分支的指引。
- 不链接整份 .agents，不执行技能安装；只提示技能目录可达性，**不声称已验证客户端发现或版本**。技能准备仍遵循 [onboarding](../../skills/bk-audit-onboarding/references/workspace.md)。
- 不准备认证、运行配置、虚拟环境、数据库、Redis、队列或后台服务。
- 专题中的文件会被共同读写；软链接不是只读权限。只选允许共同修改的资料，敏感材料和运行输出不要放入白名单。修改/删除链接内的内容会影响来源。

## 一次性配置与安装

要求 macOS/Linux、Python 3.9+、支持 --path-format=absolute 的 Git（建议 2.31+）。
在准备长期保留、材料实际所在的源 checkout 根目录操作。以下专题名是占位示例，需替换成已审阅的真实目录；不会自动创建来源目录。

    TOOL=agent/shared/tools/worktree-bootstrap/bootstrap.py
    python3 "$TOOL" configure --source-root "$PWD" --share 'src/backend/debug/开发方案/某任务'
    python3 "$TOOL" check
    python3 "$TOOL" install-hook

多个专题重复传入 --share。配置路径为 Git 公共目录下 worktree-bootstrap/config.json。
配置对**整个仓库的 worktree** 生效：每个新 worktree 都会接入同一组批准的专题，并非自动推断当前任务。
来源必须是同一仓库的 checkout 根，不能用另一个仓库或任意目录冒充。
更新白名单需要重新列出完整列表并显式传 configure --replace；不自动移除旧链接。

之后，无论 Agent 或人正常执行 git worktree add，都会自动执行初始化。普通分支 checkout/switch 也会触发，操作可重复。
只在当前源 checkout 中运行时，材料本来就在原位置，不会把它改成链接。

## 检查、补齐与失败语义

在任何 checkout/子目录，可直接调用已安装快照，无需当前分支含源码：

    COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
    python3 "$COMMON/worktree-bootstrap/bootstrap.py" check
    python3 "$COMMON/worktree-bootstrap/bootstrap.py" apply

check 只读；apply 补齐缺失链接；异常均返回 1。
也可从含源码的 checkout 调用 python3 "$TOOL" --worktree /path/to/tree check。

- 缺失链接：check 报告；apply 创建必要父目录和链接。
- 已有正确链接：跳过；已有真实文件、目录、错误/失效链接：报告冲突，**不替换、不删除**。
- 来源缺失、来源本身是软链、来源/目标的祖先是软链：拒绝；不会自动迁移已有的整目录 debug 链接。
- 目标本身/子路径或祖先被 Git 跟踪（包括 sparse checkout 隐藏项）、或目标未被 Git 忽略：拒绝，避免损坏 checkout 或把本地资料链接提交进去。
- 专题路径不接受控制字符、隐藏路径分量、绝对路径和目录穿越。
- 单个专题冲突不阻止检查其他专题；apply 是可重复的补齐操作，**不是事务**，已创建的其他链接不会回滚。
- Git 已完成 checkout 后 hook 才执行；初始化失败打印 WARNING，但保留 Git 操作成功，不伪装回滚或阻止分支切换。自动化调用者需显式运行 check，以退出码验收。
- git worktree add --no-checkout、禁用/覆盖 hooks、某些非标准客户端创建流程不会触发。完成 checkout 后手工 apply/check，或让客户端初始化入口调用同一快照。
- 不验收前端指引、全部项目依赖、技能发现和完整开工条件；这些仍由对应端 onboarding 按任务验收。

## hook 共存、升级与停用

安装器不更改 core.hooksPath，并检查现存 worktree 的有效设置；发现定制 hooksPath、其他 post-checkout 或人工修改过的本工具 hook 时拒绝覆盖，由维护者明确集成。
pre-commit、commit-msg、pre-push 不变。仓库级 hook 是本机选择，**合并代码不等于其他成员已启用**。

升级时先审阅新版源码，再从新版 checkout 执行 install-hook，更新公共目录中的快照。不会自动跟随分支升级。
Python 解释器的绝对路径会在安装时固定；解释器失效会打印 WARNING，需要人工核对旧 hook 后重新集成，不能静默切换执行来源。

停用：先检查 Git 公共目录 hooks/post-checkout，确认它仍是本工具生成的完整内容，再只移除该文件；**不要删除整个 hooks 目录或更改全局配置**。
配置与快照可保留用于手工 check/apply。工具不提供自动删除共享资料或链接的命令；删除某个链接前须确认它确实是 symlink，只删除链接本身，不递归删除来源。
来源 checkout 移动/删除后需显式更新配置，已有链接不会自动重写。需保留同一位置，或逐个人工处理冲突。

## 验证

    python3 -m unittest discover -s agent/shared/tools/worktree-bootstrap/tests -v

测试只使用临时真实 Git 仓库，不触碰开发者的本机 hook、材料、服务或认证。无需网络或三方 Python 包。
当前程序依赖本地可信操作者，不是针对同一账号下恶意并发改动文件系统的安全沙箱；不要与其他工具同时修改同一目标目录。
