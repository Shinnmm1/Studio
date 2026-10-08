STUDIO SHIN - Wasmer 部署说明
=================================
文件 (放在项目根目录, 替换旧的):
  app.py         后台 (Flask)
  index.html        网页
  requirements.txt  依赖 (flask)
  app.yaml          用你自己的; 只需把 app.yaml.example 里的 volumes 加进去

步骤:
1. 把 app.py / index.html / requirements.txt 放进项目根目录, 覆盖旧文件.
2. 在你的 app.yaml 里加上 volumes 那几行 (见 app.yaml.example).
3. Wasmer 后台 -> Environment variables 添加:
     ADMIN_USER = StudShin
     ADMIN_PASS = 你的新密码
     SECRET     = 一长串随机字符
4. wasmer deploy
5. 打开 https://你的网址/api/health
     要看到:  "writable": true   和   "admin_pass_set": true
6. 打开网站 -> Ctrl+Shift+R -> 右上角 "登录" -> 看到绿色 "已连接服务器" -> 添加脚本 -> 刷新, 脚本还在.

如果 writable 是 false: 存储盘没有挂载, 检查 app.yaml 的 volumes.
如果 admin_pass_set 是 false: 环境变量没生效, 重新设置后再 deploy.
