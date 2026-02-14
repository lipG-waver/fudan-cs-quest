# Level 02 - Git History Detective

目标：在仓库提交历史中找到真正密码并提交。

步骤建议：
1. 查看 `Yq5x5wt0Jj_TUORp/password.txt`。
2. 使用 `git log` 找到提示“真的密码存储在这里”的提交。
3. 用 `git show <commit>:Yq5x5wt0Jj_TUORp/password.txt` 查看该版本内容。

提交示例：
```bash
python -m quest submit --answer "iamthebest"
```
