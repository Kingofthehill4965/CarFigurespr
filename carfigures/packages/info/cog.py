import logging
import sys

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from carfigures import bot_version
from carfigures.core.models import cars as carfigures
from carfigures.core.utils.transformers import EventTransform
from carfigures.core.utils.paginator import FieldPageSource, Pages
from carfigures.core.utils.tortoise import row_count_estimate
from carfigures.packages.info.components import machine_info, mention_app_command

from carfigures.settings import settings

if TYPE_CHECKING:
    from carfigures.core.bot import CarFiguresBot

log = logging.getLogger("carfigures.packages.info")


class Info(commands.GroupCog, group_name=settings.info_group_name):
    """
    Simple info commands.
    """

    def __init__(self, bot: "CarFiguresBot"):
        self.bot = bot

    @app_commands.command()
    async def ping(self, interaction: discord.Interaction):
        """
        Show the bot latency.
        """
        await interaction.response.send_message(
            f"Pong! {round(self.bot.latency * 1000)}ms", ephemeral=True
        )
    @app_commands.command()
    async def status(self, interaction: discord.Interaction):
        """
        Show information about this bot.
        """
        embed = discord.Embed(
            title=f"❑ {settings.bot_name} Bot Status",
            color=settings.default_embed_color,
        )

        cars_count = len([x for x in carfigures.values() if x.enabled])
        players_count = await row_count_estimate("player")
        cars_instances_count = await row_count_estimate("carinstance")
        contributors = "\n".join(
            [f"\u200b **⋄** {contrib}" for contrib in settings.bot_contributors]
        )
        (
            cpu_usage,
            memory_usage,
            memory_total,
            memory_percentage,
            disk_usage,
            disk_total,
            disk_percentage,
        ) = machine_info()

        assert self.bot.user
        assert self.bot.application
        if self.bot.application.install_params is None:
            invite_link = discord.utils.oauth_url(
                self.bot.application.id,
                permissions=discord.Permissions(
                    manage_webhooks=True,
                    manage_expressions=True,
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    use_external_emojis=True,
                ),
                scopes=("bot", "applications.commands"),
            )
        else:
            invite_link = discord.utils.oauth_url(
                self.bot.application.id,
                permissions=self.bot.application.install_params.permissions,
                scopes=self.bot.application.install_params.scopes,
            )

        embed.add_field(
            name="∆ Bot Info\n",
            value=f"\u200b **⋄ {settings.collectible_name.title()}s Count: ** {cars_count:,} • {cars_instances_count:,} **Caught**\n"
            f"\u200b **⋄ Player Count: ** {players_count:,}\n"
            f"\u200b **⋄ Server Count: ** {len(self.bot.guilds):,}\n"
            f"\u200b **⋄  Operating Version: [{bot_version}]({settings.repository_link})**\n\n",
            inline=False,
        )
        embed.add_field(
            name="∇ Machine Info\n",
            value=f"\u200b **⋄ CPU:** {cpu_usage}%\n"
            f"\u200b **⋄ Memory:** {memory_usage}/{memory_total}MB • {memory_percentage}%\n"
            f"\u200b **⋄ Disk:** {disk_usage}/{disk_total}GB • {disk_percentage}%\n\n",
            inline=False,
        )

        #    embed.add_field(
        #         name="⋈ Developers",
        #         value=developers,
        #         inline=True
        #    )
        embed.add_field(name="⋊ Contributors", value=contributors, inline=False)
        #    embed.add_field(
        #        name="⋋ Testers\n",
        #        value=testers,
        #        inline=True
        #    )
        embed.add_field(
            name="⋇ Links",
            value=f"[Discord server]({settings.discord_invite}) • [Invite me]({invite_link}) • "
            f"[Source code and issues]({settings.repository_link})\n"
            f"[Terms of Service]({settings.terms_of_service}) • "
            f"[Privacy policy]({settings.privacy_policy}) • "
            f"[Top.gg Link]({settings.top_gg})",
            inline=False,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        v = sys.version_info
        embed.set_footer(
            text=f"Python {v.major}.{v.minor}.{v.micro} • discord.py {discord.__version__}"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def commands(self, interaction: discord.Interaction):
        """
        Show information about the commands inside this bot, categorized by page.
        """

        assert self.bot.users
        category_to_commands = {}  # Dictionary to store commands by category

        # Group commands by cog (category)
        for cog in self.bot.cogs.values():
            for app_command in cog.walk_app_commands():
                # Use cog name as category (unchangeable by users)
                category = cog.qualified_name
                if category == "SuperUser":
                    continue
                category_to_commands.setdefault(category, []).append(app_command)

        # Create the paginated source directly using categories dictionary
        entries = []
        for category_name, app_commands in category_to_commands.items():
            sorted_commands = sorted(
                app_commands, key=lambda c: c.name
            )  # Sort commands alphabetically
            command_descriptions = {
                c.name: c.description for c in sorted_commands
            }  # Create temporary dictionary
            for app_command in sorted_commands:
                # Combine formatted command names with newlines
                command_list = "\n".join(
                    [
                        f"\u200b ⋄ {mention_app_command(c)}: {command_descriptions[c.name]}"
                        for c in sorted_commands
                    ]
                )

            # Create an entry tuple (category name as title, list of commands)
            entry = (f"**Category: {category_name}**", f"{command_list}")
            entries.append(entry)

        source = FieldPageSource(
            entries=entries, per_page=2
        )  # Adjust per_page as needed
        source.embed.title = f"{settings.bot_name} Commands list"
        source.embed.colour = settings.default_embed_color
        pages = Pages(source=source, interaction=interaction, compact=True)
        await pages.start(ephemeral=True)

    @app_commands.command()
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def events(self, interaction: discord.Interaction, event: EventTransform):
        """
        List the events inside the bot

        Parameters
        ----------
        event: Event
            The event u want to check info about!
        """
        await interaction.response.defer(thinking=True)
        content, file = await event.prepare_for_message(interaction)
        await interaction.followup.send(content=content, file=file)
        file.close()

    @app_commands.command()
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def tutorial(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """
        Displays a simple tutorial on how to use the bot.

        This command is a good starting point for new users who
        are not sure how to use the bot.
        """
        embed = discord.Embed(
            title="Tutorial",
            description="Tutorial on how to use the bot.",
            color=settings.default_embed_color,
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(
            name=f"What is {settings.bot_name}?",
            value= (
                f"{settings.bot_name} is a bot that allows you to collect {settings.collectible_name}s "
                "by catching them, trading for them, and having fun with all of our commands!"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"How can I catch a {settings.collectible_name}?",
            value=(
                f"To catch a {settings.collectible_name}, you can simply tap the blue `Catch me!` button "
                f"when a {settings.collectible_name} spawns, type the name of it, and if you get "
                "it right, it will be added to your showroom!"
            ),
            inline=False,
        )
        embed.add_field(
            name="How can I show my showroom?",
            value= (
                "To see the cars you have caught, you can\n"
                f"use the `/{settings.cars_group_name}` command!"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"How can I get more {settings.cars_group_name}?",
            value=(
                f"To get more {settings.cars_group_name}, you can simply catch "
                f"more {settings.cars_group_name}! The more {settings.cars_group_name} you catch, the "
                f"rarer the {settings.cars_group_name} you will get. You can also trade with other users "
                f"in order to get more {settings.cars_group_name}!"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def about(self, interaction: discord.Interaction):
        """
        Information about the bot (the reason it got created, and more coming soon!)
        """

        entries = []

        assert self.bot.user
        assert self.bot.application

        description = ("Brief Description", settings.bot_description)
        entries.append(description)
        descriptionblack = ("", "")
        entries.append(descriptionblack)

        history = ("History", settings.bot_history)
        entries.append(history)
        historyblack = ("", "")
        entries.append(historyblack)

        source = FieldPageSource(entries=entries, per_page=2)
        source.embed.title = f"About {settings.bot_name}"
        source.embed.colour = settings.default_embed_color
        source.embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        v = sys.version_info
        source.embed.set_footer(
            text=f"Python {v.major}.{v.minor}.{v.micro} • discord.py {discord.__version__}"
        )
        pages = Pages(source=source, interaction=interaction, compact=True)
        await pages.start(ephemeral=True)
