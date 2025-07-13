import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import re

class MessageForwardCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_manager = bot.admin_manager
        self.forward_manager = bot.message_forward_manager
        self.logger = bot.logger
    
    @app_commands.command(name="设置消息转发", description="设置消息转发规则（将源频道的消息转发到目标频道）")
    @app_commands.describe(
        源频道="要监听的源频道",
        目标频道="要转发到的目标频道", 
        操作类型="添加或删除转发规则"
    )
    @app_commands.choices(操作类型=[
        app_commands.Choice(name="添加转发规则", value="add"),
        app_commands.Choice(name="删除转发规则", value="remove")
    ])
    async def setup_forward(
        self, 
        interaction: discord.Interaction, 
        源频道: discord.TextChannel,
        目标频道: discord.TextChannel,
        操作类型: app_commands.Choice[str]
    ):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查权限
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        source_channel_id = 源频道.id
        target_channel_id = 目标频道.id
        
        # 检查源频道权限
        if not self.forward_manager.can_access_channel(源频道, interaction.user):
            await interaction.response.send_message("❌ 您没有访问源频道的权限！", ephemeral=True)
            return
        
        # 检查目标频道权限
        target_valid, target_channel_obj = self.forward_manager.is_valid_channel(self.bot, target_channel_id)
        if not target_valid:
            await interaction.response.send_message("❌ 机器人无法访问目标频道或目标频道无效！", ephemeral=True)
            return
        
        # 检查是否是同一个频道
        if source_channel_id == target_channel_id:
            await interaction.response.send_message("❌ 源频道和目标频道不能是同一个频道！", ephemeral=True)
            return
        
        if 操作类型.value == "add":
            # 添加转发规则
            source_guild_id = 源频道.guild.id if 源频道.guild else None
            target_guild_id = 目标频道.guild.id if 目标频道.guild else None
            
            success = self.forward_manager.add_forward_rule(
                source_channel_id, target_channel_id, 
                source_guild_id, target_guild_id, user_id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 转发规则添加成功",
                    description=f"**源频道：** {源频道.mention}\n**目标频道：** {目标频道.mention}",
                    color=0x00ff00
                )
                embed.add_field(
                    name="📝 说明", 
                    value="现在源频道中的所有消息都会自动转发到目标频道", 
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 添加转发规则失败！可能是规则已存在。", ephemeral=True)
        
        elif 操作类型.value == "remove":
            # 删除转发规则
            success = self.forward_manager.remove_forward_rule(source_channel_id, target_channel_id, user_id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 转发规则删除成功",
                    description=f"**源频道：** {源频道.mention}\n**目标频道：** {目标频道.mention}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 删除转发规则失败！规则可能不存在或您没有权限删除。", ephemeral=True)
    
    @app_commands.command(name="查看转发规则", description="查看您创建的所有消息转发规则")
    async def list_forward_rules(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查权限
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        rules = self.forward_manager.get_user_forward_rules(user_id)
        
        if not rules:
            await interaction.response.send_message("📋 您还没有创建任何转发规则。", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 您的消息转发规则", color=0x0099ff)
        
        for i, rule in enumerate(rules, 1):
            source_channel = self.bot.get_channel(rule['source_channel_id'])
            target_channel = self.bot.get_channel(rule['target_channel_id'])
            
            source_name = source_channel.mention if source_channel else f"未知频道 (ID: {rule['source_channel_id']})"
            target_name = target_channel.mention if target_channel else f"未知频道 (ID: {rule['target_channel_id']})"
            
            status = "🟢 启用" if rule['is_active'] else "🔴 禁用"
            
            embed.add_field(
                name=f"规则 {i} - {status}",
                value=f"源频道：{source_name}\n目标频道：{target_name}\n创建时间：{rule['created_at'][:19]}",
                inline=False
            )
        
        # 添加管理视图
        view = ForwardRuleManageView(self.forward_manager, user_id, rules)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="跨服务器转发", description="设置跨服务器的消息转发（通过频道ID）")
    @app_commands.describe(
        源频道id="源频道的ID",
        目标频道id="目标频道的ID",
        操作类型="添加或删除转发规则"
    )
    @app_commands.choices(操作类型=[
        app_commands.Choice(name="添加转发规则", value="add"),
        app_commands.Choice(name="删除转发规则", value="remove")
    ])
    async def cross_server_forward(
        self, 
        interaction: discord.Interaction, 
        源频道id: str,
        目标频道id: str,
        操作类型: app_commands.Choice[str]
    ):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查权限
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        # 验证ID格式
        try:
            source_channel_id = int(源频道id)
            target_channel_id = int(目标频道id)
        except ValueError:
            await interaction.response.send_message("❌ 频道ID格式无效！请输入有效的数字ID。", ephemeral=True)
            return
        
        # 检查是否是同一个频道
        if source_channel_id == target_channel_id:
            await interaction.response.send_message("❌ 源频道和目标频道不能是同一个频道！", ephemeral=True)
            return
        
        # 验证源频道
        source_valid, source_channel = self.forward_manager.is_valid_channel(self.bot, source_channel_id)
        if not source_valid:
            await interaction.response.send_message("❌ 无法访问源频道！请检查频道ID是否正确且机器人在该服务器中。", ephemeral=True)
            return
        
        # 验证目标频道
        target_valid, target_channel = self.forward_manager.is_valid_channel(self.bot, target_channel_id)
        if not target_valid:
            await interaction.response.send_message("❌ 无法访问目标频道！请检查频道ID是否正确且机器人在该服务器中。", ephemeral=True)
            return
        
        # 检查用户对源频道的权限
        source_member = source_channel.guild.get_member(user_id)
        if not source_member or not self.forward_manager.can_access_channel(source_channel, source_member):
            await interaction.response.send_message("❌ 您没有访问源频道的权限！", ephemeral=True)
            return
        
        if 操作类型.value == "add":
            # 添加转发规则
            success = self.forward_manager.add_forward_rule(
                source_channel_id, target_channel_id, 
                source_channel.guild.id, target_channel.guild.id, user_id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 跨服务器转发规则添加成功",
                    description=f"**源频道：** {source_channel.mention} ({source_channel.guild.name})\n**目标频道：** {target_channel.mention} ({target_channel.guild.name})",
                    color=0x00ff00
                )
                embed.add_field(
                    name="📝 说明", 
                    value="现在源频道中的所有消息都会自动转发到目标频道", 
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 添加转发规则失败！可能是规则已存在。", ephemeral=True)
        
        elif 操作类型.value == "remove":
            # 删除转发规则
            success = self.forward_manager.remove_forward_rule(source_channel_id, target_channel_id, user_id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 跨服务器转发规则删除成功",
                    description=f"**源频道：** {source_channel.mention} ({source_channel.guild.name})\n**目标频道：** {target_channel.mention} ({target_channel.guild.name})",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 删除转发规则失败！规则可能不存在或您没有权限删除。", ephemeral=True)

class ForwardRuleManageView(discord.ui.View):
    def __init__(self, forward_manager, user_id, rules):
        super().__init__(timeout=300)
        self.forward_manager = forward_manager
        self.user_id = user_id
        self.rules = rules
        
        # 添加规则管理选择器
        if rules:
            options = []
            for i, rule in enumerate(rules):
                status = "启用" if rule['is_active'] else "禁用"
                label = f"规则 {i+1} - {status}"
                description = f"源: {rule['source_channel_id']} -> 目标: {rule['target_channel_id']}"
                options.append(discord.SelectOption(
                    label=label[:100],  # Discord限制
                    description=description[:100],  # Discord限制
                    value=str(rule['id'])
                ))
            
            if len(options) <= 25:  # Discord限制
                self.add_item(RuleSelect(forward_manager, user_id, options))

class RuleSelect(discord.ui.Select):
    def __init__(self, forward_manager, user_id, options):
        super().__init__(placeholder="选择要管理的转发规则...", options=options)
        self.forward_manager = forward_manager
        self.user_id = user_id
    
    async def callback(self, interaction: discord.Interaction):
        rule_id = int(self.values[0])
        
        # 获取规则详情
        rules = self.forward_manager.get_user_forward_rules(self.user_id)
        selected_rule = next((rule for rule in rules if rule['id'] == rule_id), None)
        
        if not selected_rule:
            await interaction.response.send_message("❌ 找不到选中的规则！", ephemeral=True)
            return
        
        # 创建管理按钮
        view = RuleActionView(self.forward_manager, self.user_id, selected_rule)
        
        embed = discord.Embed(
            title="🔧 规则管理",
            description=f"**规则ID：** {rule_id}\n**状态：** {'🟢 启用' if selected_rule['is_active'] else '🔴 禁用'}",
            color=0x0099ff
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RuleActionView(discord.ui.View):
    def __init__(self, forward_manager, user_id, rule):
        super().__init__(timeout=60)
        self.forward_manager = forward_manager
        self.user_id = user_id
        self.rule = rule
        
        # 根据当前状态设置按钮
        if rule['is_active']:
            self.toggle_button.label = "禁用规则"
            self.toggle_button.emoji = "🔴"
            self.toggle_button.style = discord.ButtonStyle.secondary
        else:
            self.toggle_button.label = "启用规则"
            self.toggle_button.emoji = "🟢"
            self.toggle_button.style = discord.ButtonStyle.primary
    
    @discord.ui.button(label="切换状态", style=discord.ButtonStyle.primary)
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_status = not self.rule['is_active']
        success = self.forward_manager.toggle_forward_rule(self.rule['id'], self.user_id, new_status)
        
        if success:
            status_text = "启用" if new_status else "禁用"
            await interaction.response.send_message(f"✅ 已{status_text}转发规则！", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 切换规则状态失败！", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MessageForwardCommands(bot))