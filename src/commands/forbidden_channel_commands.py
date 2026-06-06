import discord
from discord.ext import commands
from discord import app_commands

class ForbiddenChannelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_manager = bot.admin_manager
        self.forbidden_manager = bot.forbidden_channel_manager
        self.logger = bot.logger

    @app_commands.command(name="违规频道", description="管理违规频道：在此发言的用户将被自动踢出并清除7天消息（仅超级管理员）")
    @app_commands.describe(操作类型="选择操作", 频道="目标频道")
    @app_commands.choices(操作类型=[
        app_commands.Choice(name="添加", value="add"),
        app_commands.Choice(name="移除", value="remove"),
        app_commands.Choice(name="查看", value="view")
    ])
    async def forbidden_channel(
        self,
        interaction: discord.Interaction,
        操作类型: app_commands.Choice[str],
        频道: discord.TextChannel = None
    ):
        if not self.admin_manager.is_super_admin(interaction.user.id):
            await interaction.response.send_message("❌ 只有超级管理员才能执行此命令！", ephemeral=True)
            return

        if 操作类型.value == "add":
            if not 频道:
                await interaction.response.send_message("❌ 请指定频道！", ephemeral=True)
                return
            success = self.forbidden_manager.add_channel(interaction.guild.id, 频道.id, interaction.user.id)
            if success:
                await interaction.response.send_message(
                    f"✅ 已将 {频道.mention} 设为违规频道，在此发言的用户将被自动踢出并清除7天内消息。",
                    ephemeral=True
                )
                self.logger.info(f"超级管理员 {interaction.user.id} 添加违规频道 {频道.id}")
            else:
                await interaction.response.send_message("❌ 添加失败，可能已存在！", ephemeral=True)

        elif 操作类型.value == "remove":
            if not 频道:
                await interaction.response.send_message("❌ 请指定频道！", ephemeral=True)
                return
            success = self.forbidden_manager.remove_channel(interaction.guild.id, 频道.id)
            if success:
                await interaction.response.send_message(f"✅ 已移除 {频道.mention} 的违规频道设置。", ephemeral=True)
                self.logger.info(f"超级管理员 {interaction.user.id} 移除违规频道 {频道.id}")
            else:
                await interaction.response.send_message("❌ 移除失败，该频道可能不在违规列表中！", ephemeral=True)

        elif 操作类型.value == "view":
            channel_ids = self.forbidden_manager.get_channels(interaction.guild.id)
            if not channel_ids:
                await interaction.response.send_message("📋 当前没有设置违规频道。", ephemeral=True)
                return
            lines = []
            for cid in channel_ids:
                ch = interaction.guild.get_channel(cid)
                lines.append(ch.mention if ch else f"已删除频道 (ID: {cid})")
            embed = discord.Embed(
                title="🚫 违规频道列表",
                description="\n".join(lines),
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ForbiddenChannelCommands(bot))
