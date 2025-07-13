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
    
    @app_commands.command(name="消息转发", description="设置消息转发规则（支持跨服务器）")
    @app_commands.describe(
        源频道="要监听的源频道（可输入频道或频道ID）",
        目标频道="要转发到的目标频道（可输入频道或频道ID）", 
        操作类型="添加或删除转发规则"
    )
    @app_commands.choices(操作类型=[
        app_commands.Choice(name="添加转发规则", value="add"),
        app_commands.Choice(name="删除转发规则", value="remove")
    ])
    async def message_forward(
        self, 
        interaction: discord.Interaction, 
        源频道: str,
        目标频道: str,
        操作类型: app_commands.Choice[str]
    ):
        user_id = interaction.user.id
        member_roles = [role.id for role in interaction.user.roles]
        
        # 检查权限
        if not self.admin_manager.can_use_admin_commands(user_id, member_roles):
            await interaction.response.send_message("❌ 您没有权限执行此命令！", ephemeral=True)
            return
        
        # 解析源频道
        source_channel_id = self.parse_channel_input(源频道)
        if not source_channel_id:
            await interaction.response.send_message("❌ 源频道格式无效！请输入 #频道名 或频道ID", ephemeral=True)
            return
        
        # 解析目标频道
        target_channel_id = self.parse_channel_input(目标频道)
        if not target_channel_id:
            await interaction.response.send_message("❌ 目标频道格式无效！请输入 #频道名 或频道ID", ephemeral=True)
            return
        
        # 检查是否是同一个频道
        if source_channel_id == target_channel_id:
            await interaction.response.send_message("❌ 源频道和目标频道不能是同一个频道！", ephemeral=True)
            return
        
        # 验证源频道
        source_valid, source_channel = self.forward_manager.is_valid_channel(self.bot, source_channel_id)
        if not source_valid:
            await interaction.response.send_message("❌ 无法访问源频道！请检查频道是否存在且机器人在该服务器中。", ephemeral=True)
            return
        
        # 验证目标频道
        target_valid, target_channel = self.forward_manager.is_valid_channel(self.bot, target_channel_id)
        if not target_valid:
            await interaction.response.send_message("❌ 无法访问目标频道！请检查频道是否存在且机器人在该服务器中。", ephemeral=True)
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
                # 判断是否跨服务器
                cross_server = source_channel.guild.id != target_channel.guild.id
                title = "✅ 跨服务器转发规则添加成功" if cross_server else "✅ 转发规则添加成功"
                
                embed = discord.Embed(title=title, color=0x00ff00)
                embed.add_field(
                    name="📤 源频道",
                    value=f"{source_channel.mention} ({source_channel.guild.name})",
                    inline=False
                )
                embed.add_field(
                    name="📥 目标频道", 
                    value=f"{target_channel.mention} ({target_channel.guild.name})",
                    inline=False
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
                embed = discord.Embed(title="✅ 转发规则删除成功", color=0xff0000)
                embed.add_field(
                    name="📤 源频道",
                    value=f"{source_channel.mention} ({source_channel.guild.name})",
                    inline=False
                )
                embed.add_field(
                    name="📥 目标频道", 
                    value=f"{target_channel.mention} ({target_channel.guild.name})",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 删除转发规则失败！规则可能不存在或您没有权限删除。", ephemeral=True)
    
    def parse_channel_input(self, channel_input: str) -> Optional[int]:
        """解析频道输入（支持频道提及和频道ID）"""
        # 移除空格
        channel_input = channel_input.strip()
        
        # 处理频道提及 <#123456789>
        mention_pattern = r'<#(\d+)>'
        mention_match = re.match(mention_pattern, channel_input)
        if mention_match:
            return int(mention_match.group(1))
        
        # 处理纯数字ID
        if channel_input.isdigit():
            return int(channel_input)
        
        return None

async def setup(bot):
    await bot.add_cog(MessageForwardCommands(bot))