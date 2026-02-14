# 🎮 Fudan CS Quest - 复旦计算机新手闯关

> 一个为复旦（也可扩展到其他高校）大一新生设计的编程能力闯关游戏。

## ✨ 现在完全使用 CLI 方案（方案A）

本项目已改为**单入口命令行闯关体验**，不再依赖手动解压缩包。

你只需要记住一个入口：

```bash
python -m quest <command>
```

## 🚀 快速开始

### 1) 初始化进度

```bash
python -m quest start
```

### 2) 查看当前关卡

```bash
python -m quest run
```

### 3) 提交答案

```bash
python -m quest submit --answer "你的答案"
```

### 4) 如果卡住，获取提示

```bash
python -m quest hint
```

### 5) 查看进度

```bash
python -m quest status
```

---

## 🧠 你将训练到的真实能力

- 文件系统探索与命令行检索
- Git 提交历史取证（`git log` / `git show`）
- 黑盒测试与实验设计
- 反思与工程化改进表达

## 📁 项目结构（核心）

```text
quest/                 # CLI 引擎
levels/
  registry.json        # 关卡顺序
  level_01/...         # 每关 manifest/task/checker
  level_02/...
  level_03/...
  level_04/...
.quest/state.json      # 本地闯关状态（自动生成）
```

## 👥 面向谁

- 复旦大一新生
- 对项目开发感兴趣的同学
- 希望加入开源协作并练习工程能力的同学

欢迎在后续补充贡献指南与更多关卡内容。
