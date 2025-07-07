# Discord 高权限管理机器人

一个具有高级权限管理功能的Discord机器人，支持角色管理和消息删除的双重确认机制。

## 功能特点

- **超级管理员系统**：通过配置文件指定超级管理员
- **角色管理**：超级管理员可以添加/移除管理员角色
- **双重确认删除**：删除消息需要两名管理员确认
- **完整日志记录**：所有操作都会被记录
- **清晰的代码架构**：模块化设计，易于维护和扩展

## 文件结构

```
gaowei/
├── config.ini              # 配置文件
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖包列表
├── admin_data.json         # 管理员数据存储（运行时生成）
├── logs/                   # 日志文件夹（运行时生成）
└── src/
    ├── config.py           # 配置解析器
    ├── logger.py           # 日志系统
    ├── admin_manager.py    # 管理员管理系统
    └── commands.py         # 斜杠命令处理
```

## 配置文件说明

程序首次运行时会自动创建 `config.ini` 配置文件。你需要编辑此文件并设置：

1. **机器人令牌**: 从 [Discord开发者门户](https://discord.com/developers/applications) 获取
2. **超级管理员ID**: 你的Discord用户ID（需要开启开发者模式）

### 配置示例：
```ini
[bot]
token=你的机器人令牌
prefix=!
description=Discord Bot Framework
activity_type=playing
activity_name=with Discord.py

[logging]
level=INFO
format=%(asctime)s [%(levelname)s] %(name)s: %(message)s
file_enabled=true
console_enabled=true

[admin]
super_admin_id=你的Discord用户ID
```

## 安装和运行

1. **克隆项目**：
```bash
git clone <项目地址>
cd gaowei
```

2. **安装依赖**：
```bash
pip install -r requirements.txt
```

3. **首次运行**（会自动生成配置文件）：
```bash
python main.py
```

4. **编辑配置文件** `config.ini`，设置你的机器人令牌和超级管理员ID

5. **再次运行机器人**：
```bash
python main.py
```

## 可用命令

### 超级管理员专用命令
- `/添加管理员角色` - 添加一个管理员角色
- `/移除管理员角色` - 移除一个管理员角色

### 管理员命令
- `/查看管理员角色` - 查看当前所有管理员角色
- `/删除帖子` - 删除指定帖子（需要另一位管理员确认）
- `/创建频道` - 创建仅限管理员和指定用户可见的频道（需要另一位管理员确认）

## 权限说明

1. **超级管理员**：配置文件中指定的用户，拥有所有权限
2. **管理员**：拥有指定角色的用户，可以使用删除消息等功能
3. **普通用户**：无法使用任何管理命令

## 安全特性

- 删除消息需要两名管理员确认（发起人不能确认自己的请求）
- 所有操作都会记录到日志文件
- 配置文件中的敏感信息需要妥善保护
- 管理员角色数据自动保存到本地文件

## 注意事项

⚠️ **重要提醒**：
- 请妥善保管配置文件中的机器人令牌
- 建议定期备份 `admin_data.json` 文件
- 机器人需要相应的Discord权限才能正常工作
- 请确保超级管理员ID设置正确