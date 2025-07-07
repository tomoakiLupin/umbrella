import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
import re

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_manager = bot.admin_manager
        self.logger = bot.logger
        self.pending_deletions = {}  # 存储待删除的消息请求
    
    @app_commands.command(name="添加管理员角色", description="添加一个管理员角色（仅超级管理员可用）")
    @app_commands.describe(角色="要添加为管理员的角色")
    async def add_admin_role(self, interaction: discord.Interaction, 角色: discord.Role):
        user_id = interaction.user.id
        
        if not self.admin_manager.is_super_admin(user_id):
            await interaction.response.send_message("❌ 只有超级管理员才能执行此命令！", ephemeral=True)
            return
        
        if self.admin_manager.add_admin_role(user_id, 角色.id):
            await interaction.response.send_message(f"✅ 成功添加管理员角色：{角色.name}", ephemeral=True)
            self.logger.info(f"超级管理员 {user_id} 添加了管理员角色 {角色.name} ({角色.id})")
        else:
            await interaction.response.send_message(f"⚠️ 角色 {角色.name} 已经是管理员角色了！", ephemeral=True)
    
    @app_commands.command(name="移除管理员角色", description="移除一个管理员角色（仅超级管理员可用）")
    @app_commands.describe(角色="要移除管理员权限的角色")
    async def remove_admin_role(self, interaction: discord.Interaction, 角色: discord.Role):
        user_id = interaction.user.id
        
        if not self.admin_manager.is_super_admin(user_id):
            await interaction.response.send_message("❌ 只有超级管理员才能执行此命令！", ephemeral=True)
            return
        
        if self.admin_manager.remove_admin_role(user_id, 角色.id):
            await interaction.response.send_message(f"✅ 成功移除管理员角色：{角色.name}", ephemeral=True)
            self.logger.info(f"超级管理员 {user_id} 移除了管理员角色 {角色.name} ({角色.id})")
        else:
            await interaction.response.send_message(f"⚠️ 角色 {角色.name} 不是管理员角色！", ephemeral=True)
    
    @app_commands.command(name="查看管理员角色", description="查看当前所有管理员角色")
    async def list_admin_roles(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        admin_roles = self.admin_manager.get_admin_roles()
        
        if not admin_roles:
            await interaction.response.send_message("📋 当前没有配置管理员角色。", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 管理员角色列表", color=0x00ff00)
        role_names = []
        
        for role_id in admin_roles:
            role = interaction.guild.get_role(role_id)
            if role:
                role_names.append(f"• {role.name} (ID: {role_id})")
            else:
                role_names.append(f"• 未知角色 (ID: {role_id})")
        
        embed.description = "\n".join(role_names)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="删除帖子", description="删除指定帖子（需要另一位管理员确认）")
    @app_commands.describe(帖子链接="要删除的帖子链接")
    async def delete_post(self, interaction: discord.Interaction, 帖子链接: str):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        # 解析帖子链接
        post_info = self.parse_message_link(帖子链接)
        if not post_info:
            await interaction.response.send_message("❌ 无效的帖子链接格式！", ephemeral=True)
            return
        
        guild_id, channel_id, message_id = post_info
        
        # 检查是否是当前服务器的帖子
        if guild_id != interaction.guild.id:
            await interaction.response.send_message("❌ 只能删除当前服务器的帖子！", ephemeral=True)
            return
        
        # 获取帖子/消息
        try:
            if message_id is None:
                # 这是论坛帖子（线程）
                thread = self.bot.get_channel(channel_id)
                if not thread or not isinstance(thread, discord.Thread):
                    await interaction.response.send_message("❌ 找不到指定的帖子！", ephemeral=True)
                    return
                target_post = thread
            else:
                # 这是普通消息
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await interaction.response.send_message("❌ 找不到指定的频道！", ephemeral=True)
                    return
                
                target_post = await channel.fetch_message(message_id)
                if not target_post:
                    await interaction.response.send_message("❌ 找不到指定的帖子！", ephemeral=True)
                    return
        except discord.NotFound:
            await interaction.response.send_message("❌ 找不到指定的帖子！", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("❌ 机器人没有权限访问该频道！", ephemeral=True)
            return
        
        # 创建确认视图
        view = DeleteConfirmView(self, user_id, target_post, 帖子链接)
        
        # 根据帖子类型显示不同的预览内容
        if isinstance(target_post, discord.Thread):
            preview_text = f"帖子标题：{target_post.name}"
        else:
            preview_text = f"帖子内容预览：{target_post.content[:100]}{'...' if len(target_post.content) > 100 else ''}"
        
        embed = discord.Embed(
            title="🗑️ 删除帖子确认",
            description=f"**发起人：** {interaction.user.mention}\n**帖子链接：** {帖子链接}\n**{preview_text}**",
            color=0xff9900
        )
        embed.add_field(name="⚠️ 注意", value="确认删除按钮将在10秒后激活，届时其他管理员可以点击确认删除", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # 设置消息对象用于倒计时更新
        view.message = await interaction.original_response()
        
        # 记录删除请求
        self.pending_deletions[interaction.id] = {
            'requester': user_id,
            'target_post': target_post,
            'link': 帖子链接
        }
        
        self.logger.info(f"管理员 {user_id} 请求删除帖子：{帖子链接}")
    
    @app_commands.command(name="创建频道", description="创建一个仅限管理员和指定用户可见的频道（需要另一位管理员确认）")
    @app_commands.describe(
        频道名称="新频道的名称",
        指定用户="可以访问该频道的用户",
        分类="频道所在的分类",
        给予管理权限="是否给予指定用户管理该频道的权限",
        nsfw频道="是否为NSFW（成人内容）频道"
    )
    async def create_channel(
        self, 
        interaction: discord.Interaction, 
        频道名称: str,
        指定用户: discord.Member,
        分类: discord.CategoryChannel,
        给予管理权限: bool = False,
        nsfw频道: bool = False
    ):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        # 检查是否有权限在指定分类创建频道
        if not interaction.guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ 机器人没有管理频道的权限！", ephemeral=True)
            return
        
        # 创建确认视图
        view = CreateChannelConfirmView(
            self, user_id, 频道名称, 指定用户, 分类, 给予管理权限, nsfw频道
        )
        
        embed = discord.Embed(
            title="📁 创建频道确认",
            description=f"**发起人：** {interaction.user.mention}\n**频道名称：** {频道名称}\n**指定用户：** {指定用户.mention}\n**分类：** {分类.name}",
            color=0x0099ff
        )
        
        # 权限设置信息
        permission_text = "✅ 将给予指定用户管理该频道的权限" if 给予管理权限 else "❌ 指定用户只有查看和发言权限"
        embed.add_field(name="🔧 权限设置", value=permission_text, inline=False)
        
        # NSFW设置信息
        nsfw_text = "🔞 是，这是一个NSFW频道" if nsfw频道 else "✅ 否，这是普通频道"
        embed.add_field(name="🔞 NSFW设置", value=nsfw_text, inline=False)
        
        embed.add_field(name="⚠️ 注意", value="需要另一位管理员点击确认按钮才能创建频道", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        self.logger.info(f"管理员 {user_id} 请求创建频道：{频道名称}，指定用户：{指定用户.id}")
    
    def parse_message_link(self, link: str) -> Optional[tuple]:
        """解析Discord帖子/消息链接"""
        # 论坛帖子链接格式: https://discord.com/channels/guild_id/thread_id
        post_pattern = r'https://discord\.com/channels/(\d+)/(\d+)$'
        # 普通消息链接格式: https://discord.com/channels/guild_id/channel_id/message_id
        message_pattern = r'https://discord\.com/channels/(\d+)/(\d+)/(\d+)'
        
        # 先尝试匹配帖子链接
        post_match = re.match(post_pattern, link)
        if post_match:
            guild_id = int(post_match.group(1))
            thread_id = int(post_match.group(2))
            # 对于论坛帖子，返回格式为 (guild_id, thread_id, None)
            return guild_id, thread_id, None
        
        # 再尝试匹配消息链接
        message_match = re.match(message_pattern, link)
        if message_match:
            return int(message_match.group(1)), int(message_match.group(2)), int(message_match.group(3))
        
        return None

class DeleteConfirmView(discord.ui.View):
    def __init__(self, commands_cog, requester_id, target_post, post_link):
        super().__init__(timeout=300)  # 5分钟超时
        self.commands_cog = commands_cog
        self.requester_id = requester_id
        self.target_post = target_post
        self.post_link = post_link
        self.confirmed = False
        self.countdown_finished = False
        self.countdown_cancelled = False
        
        # 启动倒计时
        self.message = None  # 用于存储消息对象
        asyncio.create_task(self.start_countdown())
    
    @discord.ui.button(label="确认删除", style=discord.ButtonStyle.danger, emoji="🗑️", disabled=True)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查是否是管理员
        if not self.commands_cog.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此操作！", ephemeral=True)
            return
        
        # 检查是否是发起人本人
        if user_id == self.requester_id:
            await interaction.response.send_message("❌ 您不能确认自己发起的删除请求！", ephemeral=True)
            return
        
        # 检查倒计时是否完成
        if not self.countdown_finished:
            await interaction.response.send_message("❌ 确认删除按钮尚未激活，请等待倒计时结束！", ephemeral=True)
            return
        
        # 执行删除
        try:
            if isinstance(self.target_post, discord.Thread):
                # 删除论坛帖子（线程）
                await self.target_post.delete()
            else:
                # 删除普通消息
                await self.target_post.delete()
            
            success_embed = discord.Embed(
                title="✅ 帖子删除成功",
                description=f"**发起人：** <@{self.requester_id}>\n**确认人：** {interaction.user.mention}\n**帖子链接：** {self.post_link}",
                color=0x00ff00
            )
            
            await interaction.response.edit_message(embed=success_embed, view=None)
            
            self.commands_cog.logger.info(f"管理员 {user_id} 确认删除帖子：{self.post_link}")
            self.confirmed = True
            
        except discord.NotFound:
            await interaction.response.send_message("❌ 帖子已经被删除或不存在！", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ 机器人没有权限删除该帖子！", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 删除帖子时发生错误：{str(e)}", ephemeral=True)
            self.commands_cog.logger.error(f"删除帖子时发生错误：{e}")
    
    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查是否是管理员
        if not self.commands_cog.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此操作！", ephemeral=True)
            return
        
        # 标记倒计时已取消
        self.countdown_cancelled = True
        
        cancel_embed = discord.Embed(
            title="❌ 删除请求已取消",
            description=f"**发起人：** <@{self.requester_id}>\n**取消人：** {interaction.user.mention}",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
        self.commands_cog.logger.info(f"管理员 {user_id} 取消了删除请求：{self.post_link}")
    
    async def start_countdown(self):
        """等待10秒后激活确认删除按钮"""
        # 等待消息对象被设置
        while self.message is None:
            await asyncio.sleep(0.1)
        
        # 等待10秒
        await asyncio.sleep(10)
        
        # 检查是否被取消
        if self.countdown_cancelled:
            return
        
        # 激活确认删除按钮
        self.countdown_finished = True
        
        # 激活确认删除按钮
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label == "确认删除":
                item.disabled = False
                item.style = discord.ButtonStyle.danger
                break
        
        # 更新按钮状态
        try:
            await self.message.edit(view=self)
        except:
            pass
    
    async def on_timeout(self):
        if not self.confirmed and not self.countdown_cancelled:
            self.countdown_cancelled = True
            timeout_embed = discord.Embed(
                title="⏰ 删除请求超时",
                description="删除请求已超时，操作已取消。",
                color=0x888888
            )
            try:
                # 尝试编辑消息，如果失败则忽略
                await self.message.edit(embed=timeout_embed, view=None)
            except:
                pass

class CreateChannelConfirmView(discord.ui.View):
    def __init__(self, commands_cog, requester_id, channel_name, target_user, category, give_manage_permission, is_nsfw):
        super().__init__(timeout=300)  # 5分钟超时
        self.commands_cog = commands_cog
        self.requester_id = requester_id
        self.channel_name = channel_name
        self.target_user = target_user
        self.category = category
        self.give_manage_permission = give_manage_permission
        self.is_nsfw = is_nsfw
        self.confirmed = False
    
    @discord.ui.button(label="确认创建", style=discord.ButtonStyle.primary, emoji="📁")
    async def confirm_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查是否是管理员
        if not self.commands_cog.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此操作！", ephemeral=True)
            return
        
        # 检查是否是发起人本人
        if user_id == self.requester_id:
            await interaction.response.send_message("❌ 您不能确认自己发起的创建请求！", ephemeral=True)
            return
        
        
        # 执行创建频道
        try:
            # 设置权限覆盖
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),  # 禁止@everyone查看
                self.target_user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=self.give_manage_permission,
                    manage_channels=self.give_manage_permission
                )
            }
            
            # 给所有管理员角色添加权限
            admin_roles = self.commands_cog.admin_manager.get_admin_roles()
            for role_id in admin_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        manage_channels=True
                    )
            
            # 创建频道
            new_channel = await interaction.guild.create_text_channel(
                name=self.channel_name,
                category=self.category,
                overwrites=overwrites,
                nsfw=self.is_nsfw
            )
            
            success_embed = discord.Embed(
                title="✅ 频道创建成功",
                description=f"**发起人：** <@{self.requester_id}>\n**确认人：** {interaction.user.mention}\n**频道：** {new_channel.mention}\n**指定用户：** {self.target_user.mention}",
                color=0x00ff00
            )
            
            # 权限信息
            permission_text = "✅ 已给予指定用户管理权限" if self.give_manage_permission else "❌ 指定用户只有查看和发言权限"
            success_embed.add_field(name="🔧 权限", value=permission_text, inline=False)
            
            # NSFW信息
            nsfw_text = "🔞 NSFW频道" if self.is_nsfw else "✅ 普通频道"
            success_embed.add_field(name="🔞 频道类型", value=nsfw_text, inline=False)
            
            await interaction.response.edit_message(embed=success_embed, view=None)
            
            self.commands_cog.logger.info(f"管理员 {user_id} 确认创建频道：{self.channel_name}，频道ID：{new_channel.id}")
            self.confirmed = True
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ 机器人没有权限在该分类创建频道！", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 创建频道时发生错误：{str(e)}", ephemeral=True)
            self.commands_cog.logger.error(f"创建频道时发生错误：{e}")
    
    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查是否是管理员
        if not self.commands_cog.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此操作！", ephemeral=True)
            return
        
        cancel_embed = discord.Embed(
            title="❌ 创建请求已取消",
            description=f"**发起人：** <@{self.requester_id}>\n**取消人：** {interaction.user.mention}",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
        self.commands_cog.logger.info(f"管理员 {user_id} 取消了创建频道请求：{self.channel_name}")
    
    async def on_timeout(self):
        if not self.confirmed:
            timeout_embed = discord.Embed(
                title="⏰ 创建请求超时",
                description="创建请求已超时，操作已取消。",
                color=0x888888
            )
            try:
                # 需要获取消息对象来编辑，但由于没有存储，这里可能会失败
                pass
            except:
                pass

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))