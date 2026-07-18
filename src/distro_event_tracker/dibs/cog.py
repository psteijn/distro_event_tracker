"""Discord adapters for the dibs feature."""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .service import DibsAdminService


async def _call(command, *args, **kwargs):
    callback = getattr(command, "callback", command)
    return await callback(*args, **kwargs)


class DibsCog(commands.Cog, name="Dibs"):
    """Dibs prefix and slash commands.

    Command behavior currently delegates to compatibility callbacks while the
    persistence-heavy implementation is moved behind the feature service.
    """

    def __init__(self, runtime):
        self.runtime = runtime
        self.admin_service = DibsAdminService(runtime.dibs_tracker)

    def _is_admin(self, user_id: int) -> bool:
        return user_id in self.runtime.ADMIN_IDS

    def _is_dibs_channel(self, request_channel_id: int | None) -> bool:
        configured_channel_id = self.runtime.DIBS_CHANNEL_ID
        return bool(configured_channel_id) and str(request_channel_id) == str(configured_channel_id)

    async def _validate_admin_context(self, ctx: commands.Context) -> bool:
        if not self._is_dibs_channel(ctx.channel.id):
            await ctx.send("❌ This command can only be used in the designated dibs channel.")
            return False
        if not self._is_admin(ctx.author.id):
            await ctx.send("❌ You do not have permission to use this command.")
            return False
        return True

    async def _refresh_admin_summary(self, source, reason: str, details: dict):
        actor = source.user if hasattr(source, "user") else source.author
        await self.runtime.refresh_dibs_summary(
            source.guild,
            reason=reason,
            actor=str(actor.id),
            actor_name=actor.name,
            details=details,
        )

    @commands.command(name="dibs_data")
    async def dibs_data(self, ctx):
        await _call(self.runtime.dibs_data_command, ctx)

    @commands.command(name="help_dibs")
    async def help_dibs(self, ctx):
        """Show dibs commands, including admin controls."""
        embed = discord.Embed(
            title="📦 Dibs Commands",
            description="Use the listed commands in the designated dibs channel.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Claim and remove dibs",
            value=(
                "`/dibs item [quantity]` — claim an item from the list\n"
                "`/custom_dibs text [quantity]` — add a free-form claim\n"
                "`/undibs item` — remove one of your claims\n"
                "`/undibs all` — remove all of your claims"
            ),
            inline=False,
        )
        embed.add_field(
            name="Admin controls (ADMIN_IDS only)",
            value=(
                "`!admin_undibs @member item` — remove one claim for another member\n"
                "`!admin_undibs @member all` — remove all claims for that member\n"
                "The item must fully match the member's claim; for a custom dib, use "
                "only its text: `!admin_undibs @member your request`\n"
                "`!reset_dibs` — confirm before clearing every dibs claim"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @app_commands.command(
        name="dibs", description="Claim dibs on an item from the distribution list"
    )
    @app_commands.describe(item="The item you want to claim", quantity="Optional number of items")
    async def dibs(
        self, interaction: discord.Interaction, item: str, quantity: Optional[int] = None
    ):
        await _call(self.runtime.dibs, interaction, item, quantity)

    @dibs.autocomplete("item")
    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.runtime.item_autocomplete(interaction, current)

    @app_commands.command(
        name="custom_dibs", description="Claim a custom dibs entry using free-form text"
    )
    @app_commands.describe(text="The custom dibs text", quantity="Optional number of items")
    async def custom_dibs(
        self, interaction: discord.Interaction, text: str, quantity: Optional[int] = None
    ):
        await _call(self.runtime.custom_dibs, interaction, text, quantity)

    @app_commands.command(name="undibs", description="Remove one or all of your dibs")
    @app_commands.describe(item="The item to remove, or 'all' to clear all")
    async def undibs(self, interaction: discord.Interaction, item: str):
        await _call(self.runtime.undibs, interaction, item)

    @undibs.autocomplete("item")
    async def undibs_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.runtime.undibs_autocomplete(interaction, current)

    @commands.command(name="admin_undibs")
    async def admin_undibs(self, ctx, member: discord.Member, *, item: str):
        """Admin: remove one or all dibs for a member.

        Usage: !admin_undibs @member <item|all>

        The item must fully match the member's standard item name or custom
        dib text (case-insensitive). For custom dibs, use only the entered
        text, without a `Custom:` prefix. Multi-word names are accepted. Use
        `all` to clear every claim.
        """
        if not await self._validate_admin_context(ctx):
            return

        result = self.admin_service.remove_for_member(member.id, item)
        if not result.changed:
            await ctx.send(f"❌ {member.mention} has no matching dibs to remove.")
            return

        if item.casefold() == "all":
            message = f"✅ Cleared {result.removed_claims} dibs for {member.mention}."
        else:
            message = f"✅ Removed {member.mention}'s dibs on: **{result.display_item}**"
        await ctx.send(message)
        await self._refresh_admin_summary(
            ctx,
            "admin_undibs_command",
            {"member_id": member.id, "item": item, "removed_claims": result.removed_claims},
        )

    @commands.command(name="reset_dibs")
    async def reset_dibs(self, ctx):
        """Admin: confirm before clearing every dibs claim."""
        if not await self._validate_admin_context(ctx):
            return

        view = ResetDibsConfirmationView(self, ctx.author.id)
        await ctx.send("⚠️ This clears every dibs claim. Confirm to continue.", view=view)


class ResetDibsConfirmationView(discord.ui.View):
    """Invoker-only confirmation for the destructive dibs reset."""

    def __init__(self, cog: DibsCog, owner_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.owner_id = owner_id
        self.completed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "❌ Only the admin who started this reset can confirm it.", ephemeral=True
        )
        return False

    @discord.ui.button(label="Confirm reset", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.completed:
            await interaction.response.send_message(
                "This reset has already been handled.", ephemeral=True
            )
            return
        self.completed = True
        result = self.cog.admin_service.reset()
        await interaction.response.edit_message(
            content=(
                f"✅ Reset complete. Cleared {result.removed_claims} dibs "
                f"for {result.removed_members} members."
            ),
            view=None,
        )
        await self.cog._refresh_admin_summary(
            interaction,
            "reset_dibs_command",
            {"removed_claims": result.removed_claims, "removed_members": result.removed_members},
        )
        if interaction.channel:
            await interaction.channel.send(
                f"⚠️ Dibs have been reset by {interaction.user.mention}."
            )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.completed = True
        await interaction.response.edit_message(content="Reset cancelled.", view=None)
        self.stop()
