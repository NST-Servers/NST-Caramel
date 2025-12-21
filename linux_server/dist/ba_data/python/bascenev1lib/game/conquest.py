# Released under the MIT License. See LICENSE for details.
#
"""Provides the Conquest game."""

# ba_meta require api 9
# (see https://ballistica.net/wiki/meta-tag-system)

from __future__ import annotations

import random
from typing import TYPE_CHECKING, override

import bascenev1 as bs
import babase

from bascenev1lib.actor.flag import Flag
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.actor.playerspaz import PlayerSpaz
from bascenev1lib.gameutils import SharedObjects
from bascenev1lib.actor.respawnicon import RespawnIcon

if TYPE_CHECKING:
    from typing import Any, Sequence


class ConquestFlag(Flag):
    """A custom flag for use with Conquest games."""

    def __init__(self, *args: Any, **keywds: Any):
        super().__init__(*args, **keywds)
        self._team: Team | None = None
        self.light: bs.Node | None = None

        activity = bs.getactivity()
        assert isinstance(activity, ConquestGame)

        # Capture timer functionality
        self._players_contesting: list[bs.Player] = []
        self._capture_time = activity.capture_rate
        self._leave_neutral = activity.neutral_flags_on_capture
        self._previous_capturing_team: Team | None = None
        self._previous_team: Team | None = None
        self._last_capture_attempt_time: float = 0.0
        self._last_capturing_team_for_lockout: Team | None = None

        # Neutral text
        self._neutral_text_timer: bs.Timer | None = None
        self._was_recently_contested = False

        # Sound effects
        self._swip_sound = bs.getsound('swip')
        self._laser_sound = bs.getsound('laser')
        self._ticking_sound = bs.getsound('ticking')

        # Capture sound
        self._capture_sound = bs.newnode(
            'sound',
            owner=self.node,
            attrs={
                'sound': self._ticking_sound,
                'position': self.node.position,
                'positional': True,
                'volume': 0.0,
                'loop': True
            }
        )
        self._sound_volume = 0.5

        # Counter text
        self._counter = bs.newnode(
            'text',
            owner=self.node,
            attrs={
                'in_world': True,
                'scale': 0.022,
                'color': (1, 1, 0, 1),
                'h_align': 'center'
            }
        )
        self._counter.position = (
            self.node.position[0],
            self.node.position[1] + 1.3,
            self.node.position[2]
        )

        # Status text (Neutral/Recapturing/Last stand!)
        self._status_text = bs.newnode(
            'text',
            owner=self.node,
            attrs={
                'in_world': True,
                'text': 'Neutral',
                'scale': 0.011,
                'color': (1, 1, 1, 1),
                'h_align': 'center',
                'opacity': 0.0
            }
        )
        self._status_text.position = (
            self.node.position[0],
            self.node.position[1] + 0.90,
            self.node.position[2]
        )

        # Create capture region
        self._capture_region = bs.newnode(
            'region',
            attrs={
                'position': self.node.position,
                'scale': (1, 2, 1),
                'type': 'sphere',
                'materials': [activity._capture_region_mat]
            }
        )

        # Animate the counter
        bs.animate(self._counter, 'scale', {0: 0.022, 1000: 0.025, 2000: 0.022}, loop=True)

        # Animate counter color
        c_existing = self._counter.color
        c = bs.newnode(
            "combine",
            attrs={
                'input0': c_existing[0],
                'input1': c_existing[1],
                'input2': c_existing[2],
                'size': 3
            }
        )
        bs.animate(
            c,
            'input0',
            {0: c_existing[0], 3000: c_existing[1] * 0.5, 6000: c_existing[0]},
            loop=True
        )
        c.connectattr('output', self._counter, 'color')

        # Update timer
        self._update_timer = bs.Timer(0.1, bs.WeakCallPartial(self.handle_capture), repeat=True)

    @property
    def team(self) -> Team | None:
        """The team that owns this flag."""
        return self._team

    @team.setter
    def team(self, team: Team) -> None:
        """Set the team that owns this flag."""
        self._previous_team = self._team  # Store previous team before changing
        self._team = team

    def add_player_to_region(self, player: bs.Player) -> None:
        """Add a player to this flag's capture region."""
        if player not in self._players_contesting:
            self._players_contesting.append(player)

    def remove_player_from_region(self, player: bs.Player) -> None:
        """Remove a player from this flag's capture region."""
        if player in self._players_contesting:
            self._players_contesting.remove(player)

    def is_being_captured(self) -> bool:
        """Check if this flag is currently being captured."""
        return len(self._players_contesting) > 0

    def _flash_flag(self, length: float = 1.0, intensity: float = 1.0) -> None:
        """Flash the flag with light animation.

        Args:
            length: Duration of the flash effect
            intensity: Intensity multiplier for the flash
        """
        assert self.node
        assert self.light
        light = bs.newnode(
            'light',
            attrs={
                'position': self.node.position,
                'height_attenuated': False,
                'color': self.light.color,
                'radius': 0.3 * intensity,  # Scale radius with intensity
            },
        )
        bs.animate(light, 'intensity', {0: 0, 0.25: 1 * intensity, 0.5: 0}, loop=True)
        bs.timer(length, light.delete)

    def _hide_neutral_text(self) -> None:
        """Hide the neutral text after a delay."""
        self._was_recently_contested = False
        self._status_text.opacity = 0.0
        self._neutral_text_timer = None

    def handle_capture(self) -> None:
        """Handle the capture timer logic."""
        activity = bs.getactivity()
        assert isinstance(activity, ConquestGame)

        # Clean up dead players
        self._players_contesting = [
            p for p in self._players_contesting
            if p.exists() and getattr(p, 'actor', None) is not None and p.actor.is_alive()
        ]

        # Check if we have players in the region
        if self._players_contesting:
            # Group players by team
            teams_in_region = {}
            for player in self._players_contesting:
                team = player.team
                if team not in teams_in_region:
                    teams_in_region[team] = []
                teams_in_region[team].append(player)

            # If multiple teams are present, no capture happens
            if len(teams_in_region) > 1:
                self._status_text.opacity = 0.0
                self._counter.text = ""
                self._capture_sound.volume = 0.0
                return

            # Only one team is in the region
            capturing_team = list(teams_in_region.keys())[0]
            capturing_players = teams_in_region[capturing_team]

            # Check for 2-second lockout if different team tried to capture
            current_time = bs.time()
            if (self._last_capturing_team_for_lockout is not None and
                self._last_capturing_team_for_lockout != capturing_team and
                current_time - self._last_capture_attempt_time < 2.0):
                self._status_text.opacity = 0.0
                self._counter.text = ""
                self._capture_sound.volume = 0.0
                return

            self._was_recently_contested = True

            # Calculate capture speed based on number of players (max 3x speed)
            player_count = len(capturing_players)
            capture_multiplier = min(player_count, 3)

            # If the flag is neutral or belongs to the enemy, slowly capture it
            if self._team is None or self._team != capturing_team:
                # Track if this is a steal
                is_steal = (self._previous_capturing_team is not None and
                            capturing_team != self._previous_capturing_team and
                            self._capture_time < activity.capture_rate - 0.5)

                self._capture_time -= 0.1 * capture_multiplier
                self._previous_capturing_team = capturing_team
                self._last_capturing_team_for_lockout = capturing_team
                self._last_capture_attempt_time = current_time

                # Show appropriate status text
                if self._team is None:
                    self._status_text.text = 'Neutral'
                    self._status_text.opacity = 1.0
                else:
                    self._status_text.opacity = 0.0

                # Smoothly transition flag color based on capture progress
                if self.node and self.light:
                    # Calculate the capture progress (0.0 to 1.0)
                    progress = 1.0 - (self._capture_time / activity.capture_rate)

                    if self._leave_neutral and self._team is not None:
                        # Transitioning from current team to white (neutral)
                        current_team_color = self._team.color
                        target_team_color = (1, 1, 1)
                        # Make the transition color lighter
                        current_color = (
                            current_team_color[0] * (1.0 - progress) + target_team_color[0] * progress,
                            current_team_color[1] * (1.0 - progress) + target_team_color[1] * progress,
                            current_team_color[2] * (1.0 - progress) + target_team_color[2] * progress
                        )
                    else:
                        # Direct transition from current color to capturing team color
                        current_color = self._team.color if self._team is not None else (1, 1, 1)
                        target_color = capturing_team.color

                        # Determine if we're near the end of capturing (within 0.2 seconds)
                        near_completion = self._capture_time <= 0.2

                        # Make the transition color a lighter variation, but use actual team color near completion
                        if near_completion:
                            # In the final 0.2 seconds, transition directly to the actual team color
                            # Calculate how far we are in the final stretch (0.0 to 1.0)
                            final_progress = 1.0 - (self._capture_time / 0.2)

                            # Start from a slightly lighter color and go to the actual team color
                            light_factor = 0.3 * (1.0 - final_progress)  # Decreases to 0 at completion
                            light_target = (
                                min(1.0, target_color[0] + (1.0 - target_color[0]) * light_factor),
                                min(1.0, target_color[1] + (1.0 - target_color[1]) * light_factor),
                                min(1.0, target_color[2] + (1.0 - target_color[2]) * light_factor)
                            )

                            current_color = light_target
                        else:
                            # Earlier in the capture, use a lighter variation
                            # Calculate a lighter version of the target color
                            lightness_factor = 0.5 + (0.5 * (1.0 - progress))  # More progress = less lightness
                            light_target = (
                                min(1.0, target_color[0] + (1.0 - target_color[0]) * lightness_factor),
                                min(1.0, target_color[1] + (1.0 - target_color[1]) * lightness_factor),
                                min(1.0, target_color[2] + (1.0 - target_color[2]) * lightness_factor)
                            )

                            current_color = (
                                current_color[0] * (1.0 - progress) + light_target[0] * progress,
                                current_color[1] * (1.0 - progress) + light_target[1] * progress,
                                current_color[2] * (1.0 - progress) + light_target[2] * progress
                            )

                    # Apply the interpolated color
                    self.node.color = current_color
                    self.light.color = current_color
            else:
                # Same team is recapturing their own flag
                self._capture_time += 0.1 * capture_multiplier

                # Show "Recapturing..." text when the flag team is the same as the capper
                # and it isn't fully capped
                if self._capture_time < activity.capture_rate:
                    self._status_text.text = 'Recapturing...'
                    self._status_text.opacity = 1.0
                else:
                    self._status_text.opacity = 0.0

                # When recapturing, transition back to the team's original color
                if self.node and self.light:
                    # Calculate recapture progress (0.0 to 1.0)
                    progress = self._capture_time / activity.capture_rate

                    # Get current color and team color
                    current_color = self.node.color
                    team_color = capturing_team.color

                    # Interpolate back to the team's color
                    interpolated_color = (
                        current_color[0] * (1.0 - progress) + team_color[0] * progress,
                        current_color[1] * (1.0 - progress) + team_color[1] * progress,
                        current_color[2] * (1.0 - progress) + team_color[2] * progress
                    )

                    # Apply the interpolated color
                    self.node.color = interpolated_color
                    self.light.color = interpolated_color

            # Give the flag to a team (or neutralize it) if the counter hits zero
            if self._capture_time <= 0:
                # Check if this was a steal
                was_steal = (self._previous_team is not None and
                            self._previous_team != capturing_team)

                # The person who captured the flag is the owner
                if self._team is None or not self._leave_neutral:
                    self._team = capturing_team
                    self.team = capturing_team
                    self.light.color = capturing_team.color
                    self.node.color = capturing_team.color
                    self._swip_sound.play(volume=1, position=self.node.position)

                    # Flash stronger if it was a steal
                    if was_steal:
                        self._flash_flag(1.5, intensity=1.5)  # Longer and more intense flash for steals
                    else:
                        self._flash_flag(1.0)

                    activity._update_scores()
                else:
                    # If neutral flags setting is on, transition to neutral first
                    self._team = None
                    self.team = None
                    self.light.color = (1, 1, 1)
                    self.node.color = (1, 1, 1)
                    self._status_text.color = (1, 1, 1)
                    self._swip_sound.play(volume=1, position=self.node.position)
                    self._flash_flag(0.5)
                    activity._update_scores()

                # Award points to all capturing players
                for player in capturing_players:
                    activity.stats.player_scored(player, 5, screenmessage=False)

                self._capture_time = activity.capture_rate  # Reset the timer
                self._status_text.opacity = 0.0
                self._previous_capturing_team = None
            elif self._capture_time >= activity.capture_rate:
                self._capture_time = activity.capture_rate
                self._status_text.opacity = 0.0
                self._previous_capturing_team = None

            # Handle ticking sound
            if self._capture_time >= activity.capture_rate or self._capture_time <= 0:
                self._capture_sound.volume = 0.0
            else:
                self._capture_sound.volume = self._sound_volume

            # Handle the text above the flag
            self._counter.text = f"{self._capture_time:.1f}"
        else:
            # Player is no longer contesting
            self._counter.text = ""
            self._capture_sound.volume = 0.0

            # If the flag is neutral and was recently contested, keep showing "Neutral" text
            if self._team is None and self._was_recently_contested:
                self._status_text.text = 'Neutral'
                self._status_text.opacity = 1.0
                self._status_text.color = (1, 1, 1)

                # If we don't have a timer active, create one to hide the text after a delay
                if self._neutral_text_timer is None:
                    self._neutral_text_timer = bs.Timer(3.0, bs.WeakCallPartial(self._hide_neutral_text))
            elif not self._was_recently_contested:
                self._status_text.opacity = 0.0
            else:
                # Make sure recapturing text doesn't stay when no one is contesting
                self._status_text.opacity = 0.0

        # Check for last stand
        activity._check_last_stand(self)


class Player(bs.Player['Team']):
    """Our player type for this game."""

    # FIXME: We shouldn't be using customdata here
    # (but need to update respawn funcs accordingly first).
    @property
    def respawn_timer(self) -> bs.Timer | None:
        """Type safe access to standard respawn timer."""
        val = self.customdata.get('respawn_timer', None)
        assert isinstance(val, (bs.Timer, type(None)))
        return val

    @respawn_timer.setter
    def respawn_timer(self, value: bs.Timer | None) -> None:
        self.customdata['respawn_timer'] = value

    @property
    def respawn_icon(self) -> RespawnIcon | None:
        """Type safe access to standard respawn icon."""
        val = self.customdata.get('respawn_icon', None)
        assert isinstance(val, (RespawnIcon, type(None)))
        return val

    @respawn_icon.setter
    def respawn_icon(self, value: RespawnIcon | None) -> None:
        self.customdata['respawn_icon'] = value


class Team(bs.Team[Player]):
    """Our team type for this game."""

    def __init__(self) -> None:
        self.flags_held = 0


# ba_meta export bascenev1.GameActivity
class ConquestGame(bs.TeamGameActivity[Player, Team]):
    """A game where teams try to claim all flags on the map."""

    name = 'Conquest'
    description = 'Secure all flags on the map to win.'
    available_settings = [
        bs.IntChoiceSetting(
            'Time Limit',
            choices=[
                ('None', 0),
                ('1 Minute', 60),
                ('2 Minutes', 120),
                ('5 Minutes', 300),
                ('10 Minutes', 600),
                ('20 Minutes', 1200),
            ],
            default=0,
        ),
        bs.FloatChoiceSetting(
            'Respawn Times',
            choices=[
                ('Shorter', 0.25),
                ('Short', 0.5),
                ('Normal', 1.0),
                ('Long', 2.0),
                ('Longer', 4.0),
            ],
            default=1.0,
        ),

        bs.IntSetting('Capture Rate', min_value=1, default=3, increment=1),
        bs.BoolSetting('Neutral Flags on Capture', default=True),
        bs.BoolSetting('Epic Mode', default=False),
    ]

    def __init__(self, settings: dict):
        super().__init__(settings)
        shared = SharedObjects.get()
        self._scoreboard = Scoreboard()
        self._score_sound = bs.getsound('score')
        self._swipsound = bs.getsound('swip')
        self._extraflagmat = bs.Material()
        self._capture_region_mat = bs.Material()
        self._flags: list[ConquestFlag] = []
        self._epic_mode = bool(settings['Epic Mode'])
        self._time_limit = float(settings['Time Limit'])
        self.capture_rate = int(settings['Capture Rate'])
        self.neutral_flags_on_capture = bool(settings.get('Neutral Flags on Capture', True))

        # Base class overrides.
        self.slow_motion = self._epic_mode
        self.default_music = bs.MusicType.EPIC if self._epic_mode else bs.MusicType.GRAND_ROMP

        # Set up capture region material
        self._capture_region_mat.add_actions(
            conditions=('they_have_material', shared.player_material),
            actions=(
                ('modify_part_collision', 'collide', True),
                ('modify_part_collision', 'physical', False),
                ('call', 'at_connect', self._handle_region_player_connect),
                ('call', 'at_disconnect', self._handle_region_player_disconnect),
            ),
        )

    @classmethod
    def supports_session_type(cls, sessiontype: type[bs.Session]) -> bool:
        return issubclass(sessiontype, bs.DualTeamSession)

    def _handle_region_player_connect(self) -> None:
        """Handle player entering a capture region."""
        collision = bs.getcollision()
        region_node = collision.sourcenode

        try:
            player_node = collision.opposingnode
            player = player_node.getdelegate(PlayerSpaz, True).getplayer(Player, True)
            # Find which flag this region belongs to
            for flag in self._flags:
                if flag._capture_region == region_node:
                    flag.add_player_to_region(player)
                    break
        except (bs.NotFoundError, babase.NodeNotFoundError):
            return

    def _handle_region_player_disconnect(self) -> None:
        """Handle player leaving a capture region."""
        collision = bs.getcollision()
        region_node = collision.sourcenode

        try:
            player_node = collision.opposingnode
            player = player_node.getdelegate(PlayerSpaz, True).getplayer(Player, True)
            # Find which flag this region belongs to
            for flag in self._flags:
                if flag._capture_region == region_node:
                    flag.remove_player_from_region(player)
                    break
        except (bs.NotFoundError, babase.NodeNotFoundError):
            # Node may have been deleted before disconnect callback was processed
            # In this case, we need to clean up any references to dead players
            # from all flags since we can't identify which specific player left
            for flag in self._flags:
                if flag._capture_region == region_node:
                    # Clean up any dead players from this flag's region
                    flag._players_contesting = [
                        p for p in flag._players_contesting
                        if p.exists() and getattr(p, 'actor', None) is not None and p.actor.is_alive()
                    ]
                    break
            return

    def _check_last_stand(self, flag: ConquestFlag) -> None:
        """Check if this flag should show 'Last stand!' text."""
        if flag.team is None:
            return

        # Count how many flags this team has
        team_flags = sum(1 for f in self._flags if f.team == flag.team)

        # Check if other teams have all other flags
        other_teams_have_rest = True
        for f in self._flags:
            if f != flag and f.team != flag.team and f.team is not None:
                continue
            elif f != flag and f.team is None:
                other_teams_have_rest = False
                break
            elif f != flag and f.team == flag.team:
                other_teams_have_rest = False
                break

        # Show "Last stand!" if this team has only one flag and others have the rest
        if team_flags == 1 and other_teams_have_rest and flag.team is not None:
            flag._status_text.text = 'Last stand!'
            flag._status_text.color = flag.team.color
            flag._status_text.opacity = 1.0
        else:
            # Reset status text color to white
            flag._status_text.color = (1, 1, 1, 1)

    @classmethod
    def supports_session_type(cls, sessiontype: type[bs.Session]) -> bool:
        return issubclass(sessiontype, bs.DualTeamSession)

    @override
    @classmethod
    def get_supported_maps(cls, sessiontype: type[bs.Session]) -> list[str]:
        assert bs.app.classic is not None
        return bs.app.classic.getmaps('conquest')

    @override
    def get_instance_description(self) -> str | Sequence:
        return 'Secure all ${ARG1} flags.', len(self.map.flag_points)

    @override
    def get_instance_description_short(self) -> str | Sequence:
        return 'secure all ${ARG1} flags', len(self.map.flag_points)

    @override
    def on_team_join(self, team: Team) -> None:
        if self.has_begun():
            self._update_scores()

    @override
    def on_player_join(self, player: Player) -> None:
        player.respawn_timer = None

        # Spawn if this player's team has a flag or if there are neutral flags
        if player.team.flags_held > 0:
            self.spawn_player(player)
        else:
            # Check for neutral flags
            neutral_flags = [flag for flag in self._flags if flag.team is None]
            if neutral_flags:
                self.spawn_player(player)

    @override
    def on_begin(self) -> None:
        super().on_begin()
        self.setup_standard_time_limit(self._time_limit)
        self.setup_standard_powerup_drops()

        # Set up flags with marker lights.
        for i, flag_point in enumerate(self.map.flag_points):
            point = flag_point
            flag = ConquestFlag(
                position=point, touchable=False, materials=[self._extraflagmat]
            )
            self._flags.append(flag)
            Flag.project_stand(point)
            flag.light = bs.newnode(
                'light',
                owner=flag.node,
                attrs={
                    'position': point,
                    'intensity': 0.25,
                    'height_attenuated': False,
                    'radius': 0.3,
                    'color': (1, 1, 1),
                },
            )

        # Give teams a flag to start with.
        for i, team in enumerate(self.teams):
            if i < len(self._flags):  # Make sure we don't go out of bounds
                self._flags[i].team = team
                light = self._flags[i].light
                assert light
                node = self._flags[i].node
                assert node
                light.color = team.color
                node.color = team.color

        self._update_scores()

        # Initial joiners didn't spawn due to no flags being owned yet;
        # spawn them now.
        for player in self.players:
            self.spawn_player(player)

    def _update_scores(self) -> None:
        for team in self.teams:
            team.flags_held = 0
        for flag in self._flags:
            if flag.team is not None:
                flag.team.flags_held += 1
        for team in self.teams:
            if team.flags_held == len(self._flags):
                self.end_game()
            self._scoreboard.set_team_value(
                team, team.flags_held, len(self._flags)
            )

    @override
    def end_game(self) -> None:
        results = bs.GameResults()
        for team in self.teams:
            results.set_team_score(team, team.flags_held)
        self.end(results=results)

    @override
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.PlayerDiedMessage):
            # Augment standard behavior, but only if we have players.
            # (prevents errors if the last player leaves)
            if self.players:
                super().handlemessage(msg)

            # Get the player who died
            player = msg.getplayer(Player)

            # Always respawn the player, but with different logic based on flag ownership
            if player.team.flags_held > 0:
                # If team has flags, respawn normally
                self.respawn_player(player)
            else:
                # If team has no flags, check for neutral flags
                neutral_flags = [flag for flag in self._flags if flag.team is None]

                if neutral_flags:
                    # If there are neutral flags, respawn the player
                    self.respawn_player(player)
                else:
                    # Seems the other team won!
                    return
        else:
            super().handlemessage(msg)

    @override
    def spawn_player(self, player: Player) -> bs.Actor:
        # We spawn players at different places based on what flags are held.
        spaz = self.spawn_player_spaz(
            player, self._get_player_spawn_position(player)
        )

        # Check if team has only one flag and should get shields
        team_flags = [f for f in self._flags if f.team == player.team]
        if len(team_flags) == 1:
            # Check if other teams have all other flags
            other_teams_have_rest = True
            for f in self._flags:
                if f not in team_flags and f.team != player.team and f.team is not None:
                    continue
                elif f not in team_flags and f.team is None:
                    other_teams_have_rest = False
                    break
                elif f not in team_flags and f.team == player.team:
                    other_teams_have_rest = False
                    break

            # Give shield if this is truly a last stand situation
            if other_teams_have_rest and spaz.node:
                spaz.equip_shields(True, 20)

        return spaz

    def _get_player_spawn_position(self, player: Player) -> Sequence[float]:
        """Get spawn position for a player."""
        # Iterate until we find a spawn owned by this team.
        spawn_count = len(self.map.spawn_by_flag_points)

        # Get all spawns owned by this team, but skip those being captured
        team_spawns = []
        for i in range(spawn_count):
            flag = self._flags[i]
            if flag.team == player.team and not flag.is_being_captured():
                team_spawns.append(i)

        # If team has only one flag, always spawn there regardless of capture status
        if player.team.flags_held == 1:
            team_spawns = [i for i in range(spawn_count) if self._flags[i].team == player.team]

        # If the player has no owned flags or all are being captured, find alternatives
        if not team_spawns:
            # First check for enemy flags (not neutral ones)
            enemy_spawns = [
                i for i in range(spawn_count)
                if self._flags[i].team is not None and self._flags[i].team != player.team
            ]

            if enemy_spawns:
                # Spawn at a random enemy flag
                spawn = random.choice(enemy_spawns)
                pt = self.map.spawn_by_flag_points[spawn]
            else:
                # If no enemy flags, check for neutral flags
                neutral_spawns = [
                    i for i in range(spawn_count) if self._flags[i].team is None
                ]

                if neutral_spawns:
                    # Spawn at a random neutral flag
                    spawn = random.choice(neutral_spawns)
                    pt = self.map.spawn_by_flag_points[spawn]
                else:
                    # If no neutral flags either, use team index to determine spawn point
                    # This ensures teams always have a place to spawn even if they have no flags
                    team_index = self.teams.index(player.team)
                    # Use modulo to ensure we don't go out of bounds
                    spawn_index = team_index % spawn_count
                    pt = self.map.spawn_by_flag_points[spawn_index]
        else:
            # Randomly choose one of our team's flags to spawn at
            spawn = random.choice(team_spawns)
            pt = self.map.spawn_by_flag_points[spawn]

        x_range = (-0.5, 0.5) if pt[3] == 0.0 else (-pt[3], pt[3])
        z_range = (-0.5, 0.5) if pt[5] == 0.0 else (-pt[5], pt[5])
        pos = (
            pt[0] + random.uniform(*x_range),
            pt[1],
            pt[2] + random.uniform(*z_range),
        )
        return pos
