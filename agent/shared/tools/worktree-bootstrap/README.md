# Worktree 检查与资料接入

建树先看[项目指引](../../../../AGENTS.md#新建-worktree)。人和 Agent 都可以在新 worktree 可选运行以下只读检查。

    python3 agent/shared/tools/worktree-bootstrap/bootstrap.py check

它核对根和后端的项目指引及已登记的资料链接，并报告根、后端、前端 `.agents/skills` 下发现的技能文件位置，以及本地后端环境路径的状态。技能可见范围以实际客户端为准。依赖和隔离是否符合要求按[后端测试指南](../../../../src/backend/docs/testing.md#worktree-隔离)验收。

如果团队或个人已有明确要跨树共用的资料，可选用下面的白名单和 `apply` 接入。个人工作区约定可写在长期保留 checkout 的 `src/backend/debug/local-project/AGENTS.md`，并按需登记其目录。

## 边界与设计

- 默认不启用。只读代码或 checkout 不会安装 hook；需本人审阅代码、确认白名单后一次性安装。
- 源码随 Git；本机配置、程序快照和 hook 存在仓库的 Git 公共目录，不提交个人路径，不改全局配置。
- hook 执行已审阅程序的**安装快照**，不执行新分支携带的代码，旧分支没有该脚本也可初始化。
- 根/后端 AGENTS.md 必须来自当前 checkout 且被跟踪；缺失只报告，不复制主分支的指引。
- 技能准备见 [onboarding](../../skills/bk-audit-onboarding/references/workspace.md)。工具仅报告技能文件，客户端发现和版本需另行核对。
- 运行环境只报告本地路径状态。配置内容、认证、依赖及测试资源由实际环境准备步骤核对。
- 专题中的文件会被共同读写；软链接不是只读权限。只选允许共同修改的资料，敏感材料和运行输出不要放入白名单。修改/删除链接内的内容会影响来源。

## 一次性配置

要求 macOS/Linux、Python 3.9+、支持 --path-format=absolute 的 Git（建议 2.31+）。
在准备长期保留、材料实际所在的源 checkout 根目录操作。以下专题名是占位示例，需替换成已审阅的真实目录；不会自动创建来源目录。

    TOOL=agent/shared/tools/worktree-bootstrap/bootstrap.py
    python3 "$TOOL" configure --source-root "$PWD" --share 'src/backend/debug/开发方案/某任务'
    python3 "$TOOL" check

多个专题重复传入 --share。配置路径为 Git 公共目录下 worktree-bootstrap/config.json。
配置对**整个仓库的 worktree** 生效：每个新 worktree 都会接入同一组批准的专题，并非自动推断当前任务。
来源必须是同一仓库的 checkout 根，不能用另一个仓库或任意目录冒充。
更新白名单需要重新列出完整列表并显式传 configure --replace；不自动移除旧链接。

需要共享材料时，先配置白名单，再从任意客户端或 shell 调用 `apply` 和 `check`。仅核对 checkout 时可以直接运行 `check`，无需预先配置。以下命令在含工具源码的 checkout 根目录运行：

    python3 "$TOOL" --worktree /path/to/new-worktree apply
    python3 "$TOOL" --worktree /path/to/new-worktree check

在可信客户端 setup 中使用时，传入本次实际创建的 worktree。只在当前源 checkout 中运行时，材料本来就在原位置。

## 检查、补齐与失败语义

如果选择安装 hook，任何 checkout 或子目录都可直接调用已安装快照：

    COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
    python3 "$COMMON/worktree-bootstrap/bootstrap.py" check
    python3 "$COMMON/worktree-bootstrap/bootstrap.py" apply

check 只读，无白名单时仍检查当前 checkout。apply 要求已有白名单，用于补齐缺失的资料链接。指引缺失、白名单损坏或资料链接冲突返回 1。技能和运行环境路径仅作提示。
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

确认白名单并审阅工具后，可用 `python3 "$TOOL" install-hook` 开启仓库级自动接入。之后正常的 `git worktree add` 和分支 checkout/switch 都会触发材料初始化，建议仍运行 `check` 核对实际结果。

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
