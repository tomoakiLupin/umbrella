import discord
from discord.ext import commands
import asyncio
import sys
import os

# 不再需要手动添加src目录到Python路径，使用相对导入

from src.core.config import Config
from src.core.logger import Logger
from src.managers.admin_manager import AdminManager
from src.managers.owner_channel_manager import OwnerChannelManager
from src.managers.message_forward_manager import MessageForwardManager
from src.core.database import DatabaseManager

class DiscordBot(commands.Bot):
    def __init__(self):
        # 加载配置
        try:
            self.config = Config()
            
            # 检查是否配置了正确的令牌和管理员ID
            if self.config.bot_token == "YOUR_BOT_TOKEN_HERE":
                print("❌ 请在配置文件中设置正确的机器人令牌")
                print("📝 编辑 config.ini 文件，将 token 替换为您的Discord机器人令牌")
                input("按回车键退出...")
                sys.exit(1)
            
            if self.config.super_admin_id == 123456789012345678:
                print("❌ 请在配置文件中设置正确的超级管理员ID")
                print("📝 编辑 config.ini 文件，将 super_admin_id 替换为您的Discord用户ID")
                input("按回车键退出...")
                sys.exit(1)
                
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            print(f"配置文件错误：{e}")
            sys.exit(1)
        
        # 初始化日志
        self.logger_manager = Logger(self.config)
        self.logger = self.logger_manager.get_logger()
        
        # 初始化管理员管理器
        self.admin_manager = AdminManager(self.config, self.logger_manager)
        
        # 初始化服主通道管理器
        self.owner_channel_manager = OwnerChannelManager(self.config, self.logger_manager)
        
        # 初始化消息转发管理器
        self.message_forward_manager = MessageForwardManager(self.config, self.logger_manager)
        
        # 设置机器人意图
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        # 初始化机器人
        super().__init__(
            command_prefix=self.config.bot_prefix,
            description=self.config.bot_description,
            intents=intents
        )
        
        self.logger.info("机器人初始化完成")
    
    async def setup_hook(self):
        """机器人启动时的设置"""
        try:
            # 加载命令模块
            await self.load_extension('src.commands.commands')
            self.logger.info("命令模块加载完成")
            
            # 加载服主通道命令模块
            await self.load_extension('src.commands.owner_channel_commands')
            self.logger.info("服主通道命令模块加载完成")
            
            # 加载消息转发命令模块
            await self.load_extension('src.commands.message_forward_commands')
            self.logger.info("消息转发命令模块加载完成")
            
            # 同步斜杠命令
            synced = await self.tree.sync()
            self.logger.info(f"同步了 {len(synced)} 个斜杠命令")
            
        except Exception as e:
            self.logger.error(f"设置钩子时发生错误：{e}")
    
    async def on_ready(self):
        """机器人准备就绪时触发"""
        self.logger.info(f"机器人已登录：{self.user.name} (ID: {self.user.id})")
        self.logger.info(f"连接到 {len(self.guilds)} 个服务器")
        
        # 设置机器人状态
        activity_type = getattr(discord.ActivityType, self.config.activity_type, discord.ActivityType.playing)
        activity = discord.Activity(type=activity_type, name=self.config.activity_name)
        await self.change_presence(activity=activity)
        
        self.logger.info(f"机器人状态设置为：{self.config.activity_type} {self.config.activity_name}")
    
    async def on_guild_join(self, guild):
        """加入新服务器时触发"""
        self.logger.info(f"加入新服务器：{guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild):
        """离开服务器时触发"""
        self.logger.info(f"离开服务器：{guild.name} (ID: {guild.id})")
    
    async def on_command_error(self, ctx, error):
        """命令错误处理"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 您没有权限执行此命令！")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ 机器人缺少必要的权限来执行此命令！")
        else:
            self.logger.error(f"命令错误：{error}")
            await ctx.send("❌ 执行命令时发生错误！")
    
    async def on_message(self, message):
        """消息事件处理 - 包含消息转发逻辑"""
        # 忽略机器人自己的消息，防止无限循环
        if message.author.bot:
            return
        
        # 处理消息转发
        if hasattr(self, 'message_forward_manager'):
            await self.handle_message_forward(message)
        
        # 处理命令
        await self.process_commands(message)
    
    async def handle_message_forward(self, message):
        """处理消息转发"""
        try:
            # 获取源频道的转发目标
            targets = self.message_forward_manager.get_forward_targets(message.channel.id)
            
            for target_channel_id, target_guild_id, rule_id in targets:
                try:
                    # 获取目标频道
                    target_channel = self.get_channel(target_channel_id)
                    if not target_channel:
                        continue
                    
                    # 检查机器人权限
                    if not target_channel.permissions_for(target_channel.guild.me).send_messages:
                        continue
                    
                    # 创建转发消息
                    embed = discord.Embed(
                        description=message.content,
                        color=0x0099ff,
                        timestamp=message.created_at
                    )
                    
                    # 设置作者信息
                    embed.set_author(
                        name=f"{message.author.display_name}",
                        icon_url=message.author.display_avatar.url
                    )
                    
                    # 添加来源信息
                    source_info = f"#{message.channel.name}"
                    if message.guild:
                        source_info += f" ({message.guild.name})"
                    embed.set_footer(text=f"来自: {source_info}")
                    
                    # 处理附件
                    files = []
                    if message.attachments:
                        attachment_info = []
                        for attachment in message.attachments[:5]:  # 限制5个附件
                            try:
                                # 对于图片，直接在embed中显示第一张
                                if attachment.content_type and attachment.content_type.startswith('image/'):
                                    if not embed.image and len(attachment_info) == 0:
                                        embed.set_image(url=attachment.url)
                                    attachment_info.append(f"🖼️ [{attachment.filename}]({attachment.url})")
                                else:
                                    attachment_info.append(f"📎 [{attachment.filename}]({attachment.url})")
                            except:
                                attachment_info.append(f"📎 {attachment.filename}")
                        
                        if attachment_info:
                            embed.add_field(
                                name="📎 附件",
                                value="\n".join(attachment_info),
                                inline=False
                            )
                    
                    # 处理回复
                    if message.reference and message.reference.message_id:
                        try:
                            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
                            reply_content = referenced_msg.content[:100] + "..." if len(referenced_msg.content) > 100 else referenced_msg.content
                            embed.add_field(
                                name="💬 回复",
                                value=f"回复 {referenced_msg.author.display_name}: {reply_content}",
                                inline=False
                            )
                        except:
                            pass
                    
                    # 发送转发消息
                    await target_channel.send(embed=embed)
                    
                except Exception as e:
                    self.logger.error(f"转发消息到频道 {target_channel_id} 时发生错误：{e}")
                    
        except Exception as e:
            self.logger.error(f"处理消息转发时发生错误：{e}")
    
    async def on_error(self, event, *args, **kwargs):
        """全局错误处理"""
        import traceback
        self.logger.error(f"事件 {event} 发生错误：{traceback.format_exc()}")

def main():
    """主函数"""
    # 创建机器人实例
    bot = DiscordBot()
    
    try:
        # 启动机器人
        bot.run(bot.config.bot_token)
    except discord.LoginFailure:
        bot.logger.error("登录失败：无效的机器人令牌")
        sys.exit(1)
    except KeyboardInterrupt:
        bot.logger.info("收到键盘中断信号，正在关闭机器人...")
        asyncio.run(bot.close())
    except Exception as e:
        bot.logger.error(f"启动机器人时发生错误：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()