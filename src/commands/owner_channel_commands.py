import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
import re
import html
from datetime import datetime
import io

def parse_iso_datetime(iso_string):
    """解析ISO格式的日期时间字符串"""
    try:
        # 处理discord.utils.utcnow().isoformat()生成的格式
        iso_string = iso_string.replace('Z', '+00:00')
        if '+' not in iso_string and 'T' in iso_string:
            # 如果没有时区信息，假设是UTC
            iso_string += '+00:00'
        return datetime.fromisoformat(iso_string)
    except (ValueError, AttributeError):
        # 如果fromisoformat不可用或格式不对，尝试手动解析
        try:
            # 移除时区信息进行简单解析
            clean_string = iso_string.split('+')[0].split('Z')[0]
            return datetime.strptime(clean_string, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            # 最后尝试不带微秒的格式
            clean_string = iso_string.split('+')[0].split('Z')[0].split('.')[0]
            return datetime.strptime(clean_string, '%Y-%m-%dT%H:%M:%S')

class OwnerChannelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_manager = bot.admin_manager
        self.owner_channel_manager = bot.owner_channel_manager
        self.logger = bot.logger

    @app_commands.command(name="创建服主通道面板", description="创建服主通道面板（仅超级管理员可用）")
    @app_commands.describe(
        面板频道="放置服主通道面板的频道",
        服主="服主用户",
        通道分类="服主通道所在的分类",
        归档频道="归档对话记录的频道",
        审核频道="服主审核用户请求的频道",
        允许身份组="允许发起通道的身份组（用逗号分隔多个@身份组）",
        允许天数="加入服务器多少天后才能发起通道（0为无限制）"
    )
    async def create_owner_panel(
        self, 
        interaction: discord.Interaction, 
        面板频道: discord.TextChannel,
        服主: discord.Member,
        通道分类: discord.CategoryChannel,
        归档频道: discord.TextChannel,
        审核频道: discord.TextChannel,
        允许身份组: str = "",
        允许天数: int = 0
    ):
        user_id = interaction.user.id
        
        if not self.admin_manager.is_super_admin(user_id):
            await interaction.response.send_message("❌ 只有超级管理员才能执行此命令！", ephemeral=True)
            return
        
        # 检查是否已存在面板配置
        existing_config = self.owner_channel_manager.get_panel_config(interaction.guild.id)
        update_mode = existing_config is not None
        
        # 检查机器人权限
        if not interaction.guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ 机器人没有管理频道的权限！", ephemeral=True)
            return
        
        if not 面板频道.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message("❌ 机器人没有在指定面板频道发送消息的权限！", ephemeral=True)
            return
        
        if not 归档频道.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message("❌ 机器人没有在归档频道发送消息的权限！", ephemeral=True)
            return
        
        if not 审核频道.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message("❌ 机器人没有在审核频道发送消息的权限！", ephemeral=True)
            return
        
        # 解析允许身份组
        allowed_roles = []
        if 允许身份组.strip():
            # 提取所有@身份组的ID
            import re
            role_mentions = re.findall(r'<@&(\d+)>', 允许身份组)
            allowed_roles = [int(role_id) for role_id in role_mentions]
        
        # 验证允许天数
        if 允许天数 < 0:
            await interaction.response.send_message("❌ 允许天数不能为负数！", ephemeral=True)
            return
        
        # 创建或更新面板配置
        if update_mode:
            # 更新现有配置
            success = self.owner_channel_manager.update_panel_config(
                guild_id=interaction.guild.id,
                panel_channel_id=面板频道.id,
                owner_id=服主.id,
                category_id=通道分类.id,
                archive_channel_id=归档频道.id,
                review_channel_id=审核频道.id,
                allowed_roles=allowed_roles,
                allowed_days=允许天数
            )
        else:
            # 创建新配置
            success = self.owner_channel_manager.create_panel_config(
                guild_id=interaction.guild.id,
                panel_channel_id=面板频道.id,
                owner_id=服主.id,
                category_id=通道分类.id,
                archive_channel_id=归档频道.id,
                review_channel_id=审核频道.id,
                allowed_roles=allowed_roles,
                allowed_days=允许天数,
                requester_id=user_id
            )
        
        if not success:
            await interaction.response.send_message("❌ 配置面板失败！", ephemeral=True)
            return
        
        # 创建并发送面板
        try:
            embed = discord.Embed(
                title="📋 服主通道面板",
                description="有投诉或意见需要反馈？点击下方按钮创建私密通道与服主沟通。",
                color=0x0099ff
            )
            embed.add_field(
                name="📝 使用说明", 
                value="1. 点击下方「创建服主通道」按钮\n2. 在弹出的窗口中输入您的投诉或意见\n3. 系统将自动创建私密通道供您与服主沟通", 
                inline=False
            )
            embed.add_field(
                name="👑 服主", 
                value=f"{服主.mention}", 
                inline=True
            )
            embed.add_field(
                name="📁 通道分类", 
                value=f"{通道分类.name}", 
                inline=True
            )
            
            view = OwnerChannelPanelView(self.owner_channel_manager, self.logger)
            panel_message = await 面板频道.send(embed=embed, view=view)
            
            # 发送成功确认
            action_text = "更新" if update_mode else "创建"
            success_embed = discord.Embed(
                title=f"✅ 服主通道面板{action_text}成功",
                description=f"**面板频道：** {面板频道.mention}\n**服主：** {服主.mention}\n**通道分类：** {通道分类.name}\n**归档频道：** {归档频道.mention}\n**审核频道：** {审核频道.mention}",
                color=0x00ff00
            )
            
            # 显示权限设置
            if allowed_roles:
                role_names = []
                for role_id in allowed_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_names.append(role.name)
                success_embed.add_field(
                    name="👥 允许身份组", 
                    value=", ".join(role_names) if role_names else "无", 
                    inline=True
                )
            else:
                success_embed.add_field(name="👥 允许身份组", value="无限制", inline=True)
            
            success_embed.add_field(
                name="📅 允许天数", 
                value=f"{允许天数}天" if 允许天数 > 0 else "无限制", 
                inline=True
            )
            
            if update_mode:
                success_embed.add_field(
                    name="ℹ️ 说明", 
                    value="已替换之前的面板配置，新配置立即生效。", 
                    inline=False
                )
            
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            self.logger.info(f"超级管理员 {user_id} 在服务器 {interaction.guild.id} {action_text}了服主通道面板")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 发送面板时发生错误：{str(e)}", ephemeral=True)
            self.logger.error(f"发送服主通道面板时发生错误：{e}")

    @app_commands.command(name="服主通道黑名单", description="管理服主通道黑名单（超级管理员和服主可用）")
    @app_commands.describe(
        操作类型="选择要执行的操作",
        用户="要操作的用户（添加或移除时必填）"
    )
    @app_commands.choices(操作类型=[
        app_commands.Choice(name="添加到黑名单", value="add"),
        app_commands.Choice(name="从黑名单移除", value="remove"),
        app_commands.Choice(name="查看黑名单", value="view")
    ])
    async def manage_owner_channel_blacklist(
        self, 
        interaction: discord.Interaction, 
        操作类型: app_commands.Choice[str],
        用户: discord.Member = None
    ):
        user_id = interaction.user.id
        
        # 获取面板配置以检查是否为服主
        panel_config = self.owner_channel_manager.get_panel_config(interaction.guild.id)
        if not panel_config:
            await interaction.response.send_message("❌ 该服务器尚未配置服主通道面板！", ephemeral=True)
            return
        
        # 检查权限：超级管理员或服主
        is_super_admin = self.admin_manager.is_super_admin(user_id)
        is_owner = user_id == panel_config["owner_id"]
        
        if not (is_super_admin or is_owner):
            await interaction.response.send_message("❌ 只有超级管理员或服主才能执行此命令！", ephemeral=True)
            return
        
        operation = 操作类型.value
        
        if operation == "add":
            # 添加到黑名单
            if not 用户:
                await interaction.response.send_message("❌ 添加到黑名单时必须指定用户！", ephemeral=True)
                return
            
            # 检查是否已在黑名单中
            if self.owner_channel_manager.is_blacklisted(interaction.guild.id, 用户.id):
                await interaction.response.send_message(f"❌ 用户 {用户.mention} 已经在黑名单中！", ephemeral=True)
                return
            
            # 添加到黑名单
            success = self.owner_channel_manager.add_to_blacklist(interaction.guild.id, 用户.id, interaction.user.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 用户已添加到黑名单",
                    description=f"**用户：** {用户.mention} ({用户.display_name})\n**用户ID：** {用户.id}\n**操作人：** {interaction.user.mention}",
                    color=0x000000,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="📝 说明",
                    value="该用户将无法再申请服主通道，看到的错误信息为：\n\"❌ 我们尝试请求泰罗 API 遇到了速率限制，请您稍后再试。\"",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                self.logger.info(f"超级管理员 {user_id} 手动将用户 {用户.id} 添加到黑名单")
            else:
                await interaction.response.send_message("❌ 添加到黑名单失败！", ephemeral=True)
        
        elif operation == "remove":
            # 从黑名单移除
            if not 用户:
                await interaction.response.send_message("❌ 从黑名单移除时必须指定用户！", ephemeral=True)
                return
            
            # 检查是否在黑名单中
            if not self.owner_channel_manager.is_blacklisted(interaction.guild.id, 用户.id):
                await interaction.response.send_message(f"❌ 用户 {用户.mention} 不在黑名单中！", ephemeral=True)
                return
            
            # 从黑名单移除
            success = self.owner_channel_manager.remove_from_blacklist(interaction.guild.id, 用户.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 用户已从黑名单移除",
                    description=f"**用户：** {用户.mention} ({用户.display_name})\n**用户ID：** {用户.id}\n**操作人：** {interaction.user.mention}",
                    color=0x00ff00,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="📝 说明",
                    value="该用户现在可以正常申请服主通道了。",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                self.logger.info(f"超级管理员 {user_id} 将用户 {用户.id} 从黑名单中移除")
            else:
                await interaction.response.send_message("❌ 从黑名单移除失败！", ephemeral=True)
        
        elif operation == "view":
            # 查看黑名单
            blacklist = self.owner_channel_manager.get_blacklist(interaction.guild.id)
            
            if not blacklist:
                embed = discord.Embed(
                    title="📋 服主通道黑名单",
                    description="当前黑名单为空。",
                    color=0x888888
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📋 服主通道黑名单",
                color=0x000000,
                timestamp=discord.utils.utcnow()
            )
            
            user_list = []
            for blacklisted_user_id in blacklist[:20]:  # 最多显示20个
                user = interaction.guild.get_member(blacklisted_user_id)
                if user:
                    user_list.append(f"• {user.mention} ({user.display_name}) - ID: {blacklisted_user_id}")
                else:
                    user_list.append(f"• 用户ID: {blacklisted_user_id} (已离开服务器)")
            
            embed.description = "\n".join(user_list) if user_list else "黑名单为空"
            
            if len(blacklist) > 20:
                embed.add_field(
                    name="📊 统计",
                    value=f"总共 {len(blacklist)} 个用户，仅显示前20个",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 统计",
                    value=f"总共 {len(blacklist)} 个用户",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="服主通道归档", description="归档服主通道（管理员和服主可用）")
    async def archive_owner_channel(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 获取面板配置
        panel_config = self.owner_channel_manager.get_panel_config(interaction.guild.id)
        if not panel_config:
            await interaction.response.send_message("❌ 该服务器未配置服主通道面板！", ephemeral=True)
            return
        
        # 检查权限：超级管理员或服主
        is_super_admin = self.admin_manager.is_super_admin(user_id)
        is_owner = user_id == panel_config["owner_id"]
        
        if not (is_super_admin or is_owner):
            await interaction.response.send_message("❌ 只有超级管理员或服主才能执行此命令！", ephemeral=True)
            return
        
        # 检查是否是服主通道
        if not self.owner_channel_manager.is_owner_channel(interaction.channel.name):
            await interaction.response.send_message("❌ 此命令只能在服主通道中使用！", ephemeral=True)
            return
        
        # 获取通道信息
        channel_info = self.owner_channel_manager.get_owner_channel_info(interaction.channel.id)
        if not channel_info:
            await interaction.response.send_message("❌ 找不到该服主通道的记录！", ephemeral=True)
            return
        
        # 创建归档确认视图
        view = ArchiveConfirmView(
            self.owner_channel_manager, 
            self.logger, 
            interaction.channel, 
            panel_config["archive_channel_id"],
            channel_info,
            user_id
        )
        
        embed = discord.Embed(
            title="🗃️ 服主通道归档确认",
            description=f"**发起人：** {interaction.user.mention}\n**通道：** {interaction.channel.mention}",
            color=0xff9900
        )
        embed.add_field(
            name="⚠️ 注意", 
            value="归档操作将在60秒后自动执行，期间可以取消。\n归档后对话记录将保存至归档频道，此通道将被删除。", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # 设置消息对象用于倒计时更新
        view.message = await interaction.original_response()
        
        # 启动倒计时任务
        view.countdown_task = asyncio.create_task(view.start_countdown())
        
        self.logger.info(f"用户 {user_id} 在服主通道 {interaction.channel.id} 发起归档请求")


class OwnerChannelPanelView(discord.ui.View):
    def __init__(self, owner_channel_manager, logger):
        super().__init__(timeout=None)  # 面板永不超时
        self.owner_channel_manager = owner_channel_manager
        self.logger = logger

    @discord.ui.button(label="创建服主通道", style=discord.ButtonStyle.primary, emoji="📞")
    async def create_owner_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 检查面板配置
        panel_config = self.owner_channel_manager.get_panel_config(interaction.guild.id)
        if not panel_config:
            await interaction.response.send_message("❌ 服主通道面板配置不存在！", ephemeral=True)
            return
        
        # 检查用户资格
        user_roles = [role.id for role in interaction.user.roles]
        member = interaction.guild.get_member(interaction.user.id)
        join_date = member.joined_at if member else discord.utils.utcnow()
        
        eligible, reason = self.owner_channel_manager.check_user_eligibility(
            interaction.guild.id, 
            interaction.user.id, 
            user_roles, 
            join_date
        )
        
        if not eligible:
            if reason == "blacklisted":
                await interaction.response.send_message(
                    "❌ 我们尝试请求泰罗 API 遇到了速率限制，请您稍后再试。", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return
        
        # 显示投诉/意见输入模态框
        modal = ComplaintModal(self.owner_channel_manager, self.logger, panel_config)
        await interaction.response.send_modal(modal)


class ComplaintModal(discord.ui.Modal, title="提交投诉/意见"):
    def __init__(self, owner_channel_manager, logger, panel_config):
        super().__init__()
        self.owner_channel_manager = owner_channel_manager
        self.logger = logger
        self.panel_config = panel_config

    complaint_content = discord.ui.TextInput(
        label="请详细描述您的投诉或意见",
        placeholder="请在此输入您要反馈的内容...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 创建待审核请求
            request_id = self.owner_channel_manager.create_pending_request(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                complaint_content=str(self.complaint_content)
            )
            
            # 获取审核频道和服主
            review_channel = interaction.guild.get_channel(self.panel_config["review_channel_id"])
            owner = interaction.guild.get_member(self.panel_config["owner_id"])
            
            if not review_channel:
                await interaction.response.send_message("❌ 找不到审核频道！", ephemeral=True)
                return
            
            if not owner:
                await interaction.response.send_message("❌ 找不到服主用户！", ephemeral=True)
                return
            
            # 创建审核面板
            review_embed = discord.Embed(
                title="📋 服主通道申请审核",
                description=f"**申请用户：** {interaction.user.mention} ({interaction.user.display_name})\n**用户ID：** {interaction.user.id}",
                color=0xffa500,
                timestamp=discord.utils.utcnow()
            )
            review_embed.add_field(
                name="📝 投诉/意见内容",
                value=str(self.complaint_content)[:1000] + ("..." if len(str(self.complaint_content)) > 1000 else ""),
                inline=False
            )
            review_embed.add_field(
                name="👤 用户信息",
                value=f"加入时间：<t:{int(interaction.user.joined_at.timestamp())}:F>\n身份组：{', '.join([role.name for role in interaction.user.roles if role.name != '@everyone'][:3])}",
                inline=False
            )
            
            # 创建审核按钮
            review_view = ReviewRequestView(
                self.owner_channel_manager, 
                self.logger, 
                request_id, 
                self.panel_config
            )
            
            # 发送到审核频道并@服主
            await review_channel.send(
                f"👑 {owner.mention} 有新的服主通道申请需要审核",
                embed=review_embed,
                view=review_view
            )
            
            # 回复用户
            success_embed = discord.Embed(
                title="✅ 申请已提交",
                description="您的服主通道申请已提交，服主将会尽快审核。\n审核通过后，系统会自动创建专属通道供您沟通。",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            self.logger.info(f"用户 {interaction.user.id} 提交了服主通道申请，请求ID: {request_id}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 提交申请时发生错误：{str(e)}", ephemeral=True)
            self.logger.error(f"提交服主通道申请时发生错误：{e}")


class ReviewRequestView(discord.ui.View):
    def __init__(self, owner_channel_manager, logger, request_id, panel_config):
        super().__init__(timeout=86400)  # 24小时超时
        self.owner_channel_manager = owner_channel_manager
        self.logger = logger
        self.request_id = request_id
        self.panel_config = panel_config

    @discord.ui.button(label="开启", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 检查权限：只有服主可以操作
        if interaction.user.id != self.panel_config["owner_id"]:
            await interaction.response.send_message("❌ 只有服主才能审核申请！", ephemeral=True)
            return
        
        request_info = self.owner_channel_manager.get_pending_request(self.request_id)
        if not request_info:
            await interaction.response.send_message("❌ 申请记录不存在！", ephemeral=True)
            return
        
        # 创建服主通道
        try:
            user = interaction.guild.get_member(request_info["user_id"])
            if not user:
                await interaction.response.send_message("❌ 找不到申请用户！", ephemeral=True)
                return
            
            # 获取下一个通道编号
            channel_number = self.owner_channel_manager.get_next_channel_number(interaction.guild.id)
            channel_name = f"服主通道-{channel_number}"
            
            # 获取分类
            category = interaction.guild.get_channel(self.panel_config["category_id"])
            if not category:
                await interaction.response.send_message("❌ 找不到指定的通道分类！", ephemeral=True)
                return
            
            # 设置权限覆盖
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                ),
                interaction.user: discord.PermissionOverwrite(  # 服主
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            }
            
            # 创建频道
            new_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"服主通道 - 用户 {user.display_name} 的投诉/意见反馈"
            )
            
            # 记录通道信息
            self.owner_channel_manager.create_owner_channel(
                channel_id=new_channel.id,
                guild_id=interaction.guild.id,
                user_id=user.id,
                complaint_content=request_info["complaint_content"],
                channel_number=channel_number
            )
            
            # 在新频道发送投诉内容卡片
            embed = discord.Embed(
                title="📋 投诉/意见内容",
                description=request_info["complaint_content"],
                color=0xff6b6b,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="👤 提交用户", 
                value=f"{user.mention} ({user.display_name})", 
                inline=True
            )
            embed.add_field(
                name="🕒 提交时间", 
                value=f"<t:{int(parse_iso_datetime(request_info['created_at']).timestamp())}:F>", 
                inline=True
            )
            
            await new_channel.send(f"👑 {interaction.user.mention} 您有新的投诉/意见需要处理", embed=embed)
            
            # 发送欢迎消息
            welcome_embed = discord.Embed(
                title="🎉 欢迎来到服主通道",
                description=f"感谢您的反馈！{interaction.user.mention} 将会与您进行沟通。",
                color=0x00ff00
            )
            await new_channel.send(embed=welcome_embed)
            
            # 私聊通知用户
            try:
                dm_embed = discord.Embed(
                    title="✅ 服主通道申请已通过",
                    description=f"您在 **{interaction.guild.name}** 的服主通道申请已通过！\n\n**专属通道：** {new_channel.mention}\n\n请前往该频道与服主进行沟通。",
                    color=0x00ff00
                )
                await user.send(embed=dm_embed)
            except:
                pass  # 私聊失败不影响主要流程
            
            # 更新审核消息
            approved_embed = discord.Embed(
                title="✅ 申请已通过",
                description=f"**申请用户：** {user.mention}\n**审核人：** {interaction.user.mention}\n**创建频道：** {new_channel.mention}",
                color=0x00ff00,
                timestamp=discord.utils.utcnow()
            )
            
            await interaction.response.edit_message(embed=approved_embed, view=None)
            
            # 删除请求记录
            self.owner_channel_manager.delete_pending_request(self.request_id)
            
            self.logger.info(f"服主 {interaction.user.id} 通过了用户 {user.id} 的申请，创建频道 {new_channel.id}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 创建频道时发生错误：{str(e)}", ephemeral=True)
            self.logger.error(f"创建服主通道时发生错误：{e}")

    @discord.ui.button(label="不同意", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 检查权限：只有服主可以操作
        if interaction.user.id != self.panel_config["owner_id"]:
            await interaction.response.send_message("❌ 只有服主才能审核申请！", ephemeral=True)
            return
        
        # 显示拒绝原因输入框
        modal = RejectReasonModal(self.owner_channel_manager, self.logger, self.request_id, self.panel_config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="忽略", style=discord.ButtonStyle.secondary, emoji="🤐")
    async def ignore_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 检查权限：只有服主可以操作
        if interaction.user.id != self.panel_config["owner_id"]:
            await interaction.response.send_message("❌ 只有服主才能审核申请！", ephemeral=True)
            return
        
        request_info = self.owner_channel_manager.get_pending_request(self.request_id)
        if not request_info:
            await interaction.response.send_message("❌ 申请记录不存在！", ephemeral=True)
            return
        
        user = interaction.guild.get_member(request_info["user_id"])
        
        # 更新审核消息
        user_display = user.mention if user else f"用户ID: {request_info['user_id']}"
        ignored_embed = discord.Embed(
            title="🤐 申请已忽略",
            description=f"**申请用户：** {user_display}\n**审核人：** {interaction.user.mention}",
            color=0x888888,
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.edit_message(embed=ignored_embed, view=None)
        
        # 删除请求记录
        self.owner_channel_manager.delete_pending_request(self.request_id)
        
        self.logger.info(f"服主 {interaction.user.id} 忽略了用户 {request_info['user_id']} 的申请")

    @discord.ui.button(label="拉黑", style=discord.ButtonStyle.danger, emoji="🚫")
    async def blacklist_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 检查权限：只有服主可以操作
        if interaction.user.id != self.panel_config["owner_id"]:
            await interaction.response.send_message("❌ 只有服主才能审核申请！", ephemeral=True)
            return
        
        request_info = self.owner_channel_manager.get_pending_request(self.request_id)
        if not request_info:
            await interaction.response.send_message("❌ 申请记录不存在！", ephemeral=True)
            return
        
        # 添加到黑名单
        success = self.owner_channel_manager.add_to_blacklist(
            interaction.guild.id, 
            request_info["user_id"],
            interaction.user.id
        )
        
        if not success:
            await interaction.response.send_message("❌ 该用户已在黑名单中！", ephemeral=True)
            return
        
        user = interaction.guild.get_member(request_info["user_id"])
        
        # 更新审核消息
        user_display = user.mention if user else f"用户ID: {request_info['user_id']}"
        blacklisted_embed = discord.Embed(
            title="🚫 用户已拉黑",
            description=f"**申请用户：** {user_display}\n**审核人：** {interaction.user.mention}\n\n用户已被添加到黑名单，无法再次申请服主通道。",
            color=0x000000,
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.edit_message(embed=blacklisted_embed, view=None)
        
        # 删除请求记录
        self.owner_channel_manager.delete_pending_request(self.request_id)
        
        self.logger.info(f"服主 {interaction.user.id} 将用户 {request_info['user_id']} 加入黑名单")


class RejectReasonModal(discord.ui.Modal, title="拒绝申请"):
    def __init__(self, owner_channel_manager, logger, request_id, panel_config):
        super().__init__()
        self.owner_channel_manager = owner_channel_manager
        self.logger = logger
        self.request_id = request_id
        self.panel_config = panel_config

    reason = discord.ui.TextInput(
        label="请输入拒绝原因",
        placeholder="请详细说明拒绝该申请的原因...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        request_info = self.owner_channel_manager.get_pending_request(self.request_id)
        if not request_info:
            await interaction.response.send_message("❌ 申请记录不存在！", ephemeral=True)
            return
        
        user = interaction.guild.get_member(request_info["user_id"])
        
        # 私聊用户告知拒绝原因
        try:
            reject_embed = discord.Embed(
                title="❌ 服主通道申请被拒绝",
                description=f"您在 **{interaction.guild.name}** 的服主通道申请被拒绝。",
                color=0xff0000
            )
            reject_embed.add_field(
                name="📝 拒绝原因",
                value=str(self.reason),
                inline=False
            )
            reject_embed.add_field(
                name="💡 建议",
                value="您可以根据反馈调整后重新申请。",
                inline=False
            )
            
            if user:
                await user.send(embed=reject_embed)
        except:
            pass  # 私聊失败不影响主要流程
        
        # 更新审核消息
        user_display = user.mention if user else f"用户ID: {request_info['user_id']}"
        rejected_embed = discord.Embed(
            title="❌ 申请已拒绝",
            description=f"**申请用户：** {user_display}\n**审核人：** {interaction.user.mention}\n**拒绝原因：** {str(self.reason)}",
            color=0xff0000,
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.edit_message(embed=rejected_embed, view=None)
        
        # 删除请求记录
        self.owner_channel_manager.delete_pending_request(self.request_id)
        
        self.logger.info(f"服主 {interaction.user.id} 拒绝了用户 {request_info['user_id']} 的申请，原因：{str(self.reason)}")


class ArchiveConfirmView(discord.ui.View):
    def __init__(self, owner_channel_manager, logger, channel, archive_channel_id, channel_info, requester_id):
        super().__init__(timeout=70)  # 70秒超时（比倒计时多10秒）
        self.owner_channel_manager = owner_channel_manager
        self.logger = logger
        self.channel = channel
        self.archive_channel_id = archive_channel_id
        self.channel_info = channel_info
        self.requester_id = requester_id
        self.cancelled = False
        self.archived = False
        self.countdown_task = None
        
        # 启动倒计时
        self.message = None
        
    async def start_countdown(self):
        """开始60秒倒计时"""
        remaining = 60
        
        while remaining > 0:
            if self.cancelled or self.archived:
                return
                
            # 更新embed显示倒计时（每10秒更新一次显示）
            if remaining % 10 == 0:
                embed = discord.Embed(
                    title="🗃️ 服主通道归档确认",
                    description=f"**发起人：** <@{self.requester_id}>\n**通道：** {self.channel.mention}",
                    color=0xff9900
                )
                embed.add_field(
                    name="⏰ 倒计时", 
                    value=f"归档将在 **{remaining}** 秒后自动执行", 
                    inline=False
                )
                embed.add_field(
                    name="⚠️ 注意", 
                    value="归档后对话记录将保存至归档频道，此通道将被删除。", 
                    inline=False
                )
                
                try:
                    if self.message:
                        await self.message.edit(embed=embed, view=self)
                except:
                    pass
            
            await asyncio.sleep(1)
            remaining -= 1
        
        # 倒计时结束，执行归档
        if not self.cancelled and not self.archived:
            await self.execute_archive()

    async def execute_archive(self):
        """执行归档操作"""
        try:
            # 获取归档频道
            archive_channel = self.channel.guild.get_channel(self.archive_channel_id)
            if not archive_channel:
                self.logger.error(f"找不到归档频道 {self.archive_channel_id}")
                return
            
            # 获取所有消息历史
            messages = []
            async for message in self.channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # 生成HTML对话记录
            html_content = await self.generate_html_conversation(messages)
            
            # 创建归档卡片
            archive_embed = discord.Embed(
                title="📁 服主通道归档",
                description=f"**原通道：** {self.channel.name}\n**用户：** <@{self.channel_info['user_id']}>\n**通道编号：** {self.channel_info['channel_number']}",
                color=0x888888,
                timestamp=discord.utils.utcnow()
            )
            archive_embed.add_field(
                name="📋 原始投诉/意见", 
                value=self.channel_info['complaint_content'][:1000] + ("..." if len(self.channel_info['complaint_content']) > 1000 else ""), 
                inline=False
            )
            archive_embed.add_field(
                name="📊 统计信息", 
                value=f"消息总数：{len(messages)}\n创建时间：<t:{int(parse_iso_datetime(self.channel_info['created_at']).timestamp())}:F>\n归档时间：<t:{int(discord.utils.utcnow().timestamp())}:F>", 
                inline=False
            )
            
            # 发送HTML文件和卡片到归档频道
            html_bytes = io.BytesIO(html_content.encode('utf-8'))
            html_file = discord.File(
                fp=html_bytes,
                filename=f"服主通道-{self.channel_info['channel_number']}-对话记录.html"
            )
            
            await archive_channel.send(embed=archive_embed, file=html_file)
            
            # 标记为已归档
            self.owner_channel_manager.archive_owner_channel(self.channel.id)
            
            # 更新消息状态
            final_embed = discord.Embed(
                title="✅ 归档完成",
                description="对话记录已保存到归档频道，此通道将在5秒后删除。",
                color=0x00ff00
            )
            
            await self.message.edit(embed=final_embed, view=None)
            
            # 等待5秒后删除频道
            await asyncio.sleep(5)
            await self.channel.delete(reason="服主通道归档完成")
            
            self.archived = True
            self.logger.info(f"服主通道 {self.channel.id} 归档完成")
            
        except Exception as e:
            self.logger.error(f"归档服主通道时发生错误：{e}")
            
            error_embed = discord.Embed(
                title="❌ 归档失败",
                description=f"归档过程中发生错误：{str(e)}",
                color=0xff0000
            )
            
            try:
                await self.message.edit(embed=error_embed, view=None)
            except:
                pass

    async def generate_html_conversation(self, messages):
        """生成HTML格式的对话记录"""
        html_template = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>服主通道对话记录</title>
    <style>
        body {{ font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .message {{ background: white; margin: 10px 0; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .author {{ font-weight: bold; color: #5865f2; margin-bottom: 5px; }}
        .timestamp {{ font-size: 0.8em; color: #99aab5; }}
        .content {{ margin: 10px 0; line-height: 1.4; }}
        .embed {{ border-left: 4px solid #5865f2; padding: 10px; background: #f8f9fa; margin: 10px 0; border-radius: 0 5px 5px 0; }}
        .attachment {{ color: #0066cc; text-decoration: none; }}
        .bot-message {{ border-left: 4px solid #00ff00; }}
        .user-message {{ border-left: 4px solid #ff6b6b; }}
        .stats {{ background: white; padding: 15px; border-radius: 10px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📁 服主通道对话记录</h1>
        <p>通道：{channel_name}</p>
        <p>用户：{user_name}</p>
        <p>生成时间：{generation_time}</p>
    </div>
    
    <div class="messages">
        {messages_html}
    </div>
    
    <div class="stats">
        <h3>📊 统计信息</h3>
        <p>总消息数：{total_messages}</p>
        <p>时间范围：{time_range}</p>
    </div>
</body>
</html>
'''
        
        messages_html = ""
        for message in messages:
            author_name = html.escape(message.author.display_name)
            is_bot = message.author.bot
            
            message_class = "bot-message" if is_bot else "user-message"
            
            content = html.escape(message.content) if message.content else "<无文本内容>"
            
            # 处理附件
            if message.attachments:
                for attachment in message.attachments:
                    content += f'<br><a href="{html.escape(attachment.url)}" class="attachment">📎 {html.escape(attachment.filename)}</a>'
            
            # 处理嵌入
            if message.embeds:
                for embed in message.embeds:
                    embed_content = f'<div class="embed">'
                    if embed.title:
                        embed_content += f'<strong>{html.escape(embed.title)}</strong><br>'
                    if embed.description:
                        embed_content += f'{html.escape(embed.description)}<br>'
                    embed_content += '</div>'
                    content += embed_content
            
            messages_html += f"""
            <div class="message {message_class}">
                <div class="author">{author_name}</div>
                <div class="timestamp">{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}</div>
                <div class="content">{content}</div>
            </div>
            """
        
        # 填充模板
        user = self.channel.guild.get_member(self.channel_info['user_id'])
        user_name = html.escape(user.display_name if user else f"用户ID: {self.channel_info['user_id']}")
        
        time_range = "无消息" if not messages else f"{messages[0].created_at.strftime('%Y-%m-%d %H:%M:%S')} - {messages[-1].created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return html_template.format(
            channel_name=html.escape(self.channel.name),
            user_name=user_name,
            generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            messages_html=messages_html,
            total_messages=len(messages),
            time_range=time_range
        )

    @discord.ui.button(label="取消归档", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cancelled = True
        
        cancel_embed = discord.Embed(
            title="❌ 归档已取消",
            description=f"**取消人：** {interaction.user.mention}",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
        self.logger.info(f"用户 {interaction.user.id} 取消了服主通道 {self.channel.id} 的归档")

    async def on_timeout(self):
        if not self.cancelled and not self.archived:
            await self.execute_archive()

async def setup(bot):
    await bot.add_cog(OwnerChannelCommands(bot))