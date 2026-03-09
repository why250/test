---
name: Migrate to uv
overview: Guide the user to migrate from venv to uv for package management.
todos:
  - id: install-uv
    content: Install `uv` tool
    status: pending
  - id: init-uv
    content: Initialize `uv` project structure
    status: pending
  - id: add-deps
    content: Add dependencies from requirements.txt
    status: pending
  - id: verify-run
    content: Verify application runs with `uv`
    status: pending
isProject: false
---

# Migrate to uv

所有命令均在项目根目录（`d:\Users\Documents\GitHub\test`）的 PowerShell 终端中执行。

## 步骤

### 1. 安装 `uv`

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

安装完成后，**重新打开终端**，然后验证安装是否成功：

```powershell
uv --version
```

### 2. 初始化项目

在项目根目录下运行，生成 `pyproject.toml`：

```powershell
uv init
```

### 3. 添加依赖

从现有的 `requirements.txt` 导入所有依赖：

```powershell
uv add -r requirements.txt
```

### 4. 运行应用

```powershell
uv run main.py
```

### 5. 清理旧环境（可选）

确认应用运行正常后，删除旧的虚拟环境文件夹：

```powershell
Remove-Item -Recurse -Force .venv
```
