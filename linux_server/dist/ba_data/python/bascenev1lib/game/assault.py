# Released under the MIT License. See LICENSE for details.
#
"""Defines assault minigame."""

# ba_meta require api 9
# (see https://ballistica.net/wiki/meta-tag-system)

from __future__ import annotations

import random
from typing import TYPE_CHECKING, override

import bascenev1 as bs

from bascenev1lib.actor.playerspaz import PlayerSpaz
from bascenev1lib.actor.flag import Flag
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.gameutils import SharedObjects

if TYPE_CHECKING:
    from typing import Any, Sequence


class Player(bs.Player['Team']):
    """Our player type for this game."""


class Team(bs.Team[Player]):
    """Our team type for this game."""

    def __init__(self, base_pos: Sequence[float], flag: Flag) -> None:

        #: Where our base is.
        self.base_pos = base_pos

        #: Flag for this team.
        self.flag = flag

        #: Current score.
        self.score = 0

        #: Capture state for this team's base
        self.capturing_players: list[Player] = []
        self.capture_timer = 0.0
        self.capture_counter: bs.Node | None = None
        self.capture_sound: bs.Node | None = None

# ba_meta export bascenev1.GameActivity
class AssaultGame(bs.TeamGameActivity[Player, Team]):
    """Game where you score by touching the other team's flag."""

    name = 'Assault'
    description = 'Reach the enemy flag to score.'
    available_settings = [
        bs.IntSetting(
            'Score to Win',
            min_value=1,
            default=3,
        ),
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
        bs.IntSetting(
            'Capture Time',
            min_value=1,
            default=2,
            increment=1,
        ),
        bs.BoolSetting('Epic Mode', default=False),
    ]

    @override
    @classmethod
    def supports_session_type(cls, sessiontype: type[bs.Session]) -> bool:
        return issubclass(sessiontype, bs.DualTeamSession)

    @override
    @classmethod
    def get_supported_maps(cls, sessiontype: type[bs.Session]) -> list[str]:
        assert bs.app.classic is not None
        return bs.app.classic.getmaps('team_flag')

    def __init__(self, settings: dict):
        super().__init__(settings)
        self._scoreboard = Scoreboard()
        self._last_score_time = 0.0
        self._score_sound = bs.getsound('score')
        self._ticking_sound = bs.getsound('ticking')
        self._base_region_materials: dict[int, bs.Material] = {}
        self._epic_mode = bool(settings['Epic Mode'])
        self._score_to_win = int(settings['Score to Win'])
        self._time_limit = float(settings['Time Limit'])
        self._capture_time = int(settings['Capture Time'])

        self._sound_volume = 0.5

        # Base class overrides
        self.slow_motion = self._epic_mode
        self.default_music = bs.MusicType.EPIC if self._epic_mode else bs.MusicType.FORWARD_MARCH

    @override
    def get_instance_description(self) -> str | Sequence:
        if self._score_to_win == 1:
            return 'Reach the enemy flag.'
        return 'Reach the enemy flag ${ARG1} times.', self._score_to_win

    @override
    def get_instance_description_short(self) -> str | Sequence:
        if self._score_to_win == 1:
            return 'reach 1 flag'
        return 'reach ${ARG1} flags', self._score_to_win

    @override
    def create_team(self, sessionteam: bs.SessionTeam) -> Team:
        shared = SharedObjects.get()
        base_pos = self.map.get_flag_position(sessionteam.id)
        bs.newnode(
            'light',
            attrs={
                'position': base_pos,
                'intensity': 0.6,
                'height_attenuated': False,
                'volume_intensity_scale': 0.1,
                'radius': 0.1,
                'color': sessionteam.color,
            },
        )
        Flag.project_stand(base_pos)
        flag = Flag(touchable=False, position=base_pos, color=sessionteam.color)
        team = Team(base_pos=base_pos, flag=flag)

        # Initialize capture timer for this team
        team.capture_timer = self._capture_time

        # Create capture counter text for this team
        team.capture_counter = bs.newnode(
            'text',
            attrs={
                'in_world': True,
                'scale': 0.022,
                'color': (1, 1, 0, 1),
                'h_align': 'center',
                'position': (base_pos[0], base_pos[1] + 1.3, base_pos[2]),
                'text': ''
            }
        )

        # Create capture sound for this team
        team.capture_sound = bs.newnode(
            'sound',
            attrs={
                'sound': self._ticking_sound,
                'position': base_pos,
                'positional': True,
                'volume': 0.0,
                'loop': True
            }
        )

        mat = self._base_region_materials[sessionteam.id] = bs.Material()
        mat.add_actions(
            conditions=('they_have_material', shared.player_material),
            actions=(
                ('modify_part_collision', 'collide', True),
                ('modify_part_collision', 'physical', False),
                (
                    'call',
                    'at_connect',
                    bs.CallPartial(self._handle_base_connect, team),
                ),
                (
                    'call',
                    'at_disconnect',
                    bs.CallPartial(self._handle_base_disconnect, team),
                ),
            ),
        )

        bs.newnode(
            'region',
            owner=flag.node,
            attrs={
                'position': (base_pos[0], base_pos[1] + 0.75, base_pos[2]),
                'scale': (0.5, 0.5, 0.5),
                'type': 'sphere',
                'materials': [self._base_region_materials[sessionteam.id]],
            },
        )

        return team

    @override
    def on_team_join(self, team: Team) -> None:
        # Can't do this in create_team because the team's color/etc. have
        # not been wired up yet at that point.
        self._update_scoreboard()

    @override
    def on_begin(self) -> None:
        super().on_begin()
        self.setup_standard_time_limit(self._time_limit)
        self.setup_standard_powerup_drops()

        # Start capture timer update
        self._update_timer = bs.Timer(0.1, bs.WeakCallPartial(self._update_capture_timer), repeat=True)

    @override
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.PlayerDiedMessage):
            super().handlemessage(msg)  # Augment standard.
            player = msg.getplayer(Player)

            # Reset capture state for the dead player
            for team in self.teams:
                if player in team.capturing_players:
                    team.capturing_players.remove(player)

            self.respawn_player(player)
        else:
            super().handlemessage(msg)

    def _flash_base(self, team: Team, length: float = 2.0) -> None:
        light = bs.newnode(
            'light',
            attrs={
                'position': team.base_pos,
                'height_attenuated': False,
                'radius': 0.3,
                'color': team.color,
            },
        )
        bs.animate(light, 'intensity', {0: 0, 0.25: 2.0, 0.5: 0}, loop=True)
        bs.timer(length, light.delete)

    def _handle_base_connect(self, team: Team) -> None:
        try:
            spaz = bs.getcollision().opposingnode.getdelegate(PlayerSpaz, True)
        except bs.NotFoundError:
            return

        if not spaz.is_alive():
            return

        try:
            player = spaz.getplayer(Player, True)
        except bs.NotFoundError:
            return

        # If its another team's player, start capturing
        player_team = player.team
        if player_team is not team:
            if player not in team.capturing_players:
                team.capturing_players.append(player)

    def _handle_base_disconnect(self, team: Team) -> None:
        try:
            spaz = bs.getcollision().opposingnode.getdelegate(PlayerSpaz, True)
        except bs.NotFoundError:
            return

        try:
            player = spaz.getplayer(Player, True)
        except bs.NotFoundError:
            return

        if player in team.capturing_players:
            team.capturing_players.remove(player)

    def _reset_team_capture(self, team: Team) -> None:
        """Reset the capture state for a specific team."""
        team.capturing_players = []
        team.capture_timer = self._capture_time

        if team.capture_counter is not None:
            team.capture_counter.text = ""

        if team.capture_sound is not None:
            team.capture_sound.volume = 0.0

    def _update_capture_timer(self) -> None:
        """Update the capture timer and handle scoring for all teams."""
        for team in self.teams:
            # Clean up dead players
            team.capturing_players = [p for p in team.capturing_players if p.is_alive()]

            if team.capturing_players:
                # If multiple teams are in the region, contest it.
                first_team = team.capturing_players[0].team
                if any(p.team is not first_team for p in team.capturing_players):
                    self._reset_team_capture(team)
                    continue

                # Capture speed increases with more players, max 3.
                capture_multiplier = min(len(team.capturing_players), 3)
                team.capture_timer -= 0.1 * capture_multiplier

                # Update the counter text
                if team.capture_counter is not None:
                    team.capture_counter.text = f"{team.capture_timer:.1f}"

                # Score when timer reaches zero
                if team.capture_timer <= 0:
                    self._handle_score(team)
                # Handle ticking sound
                elif team.capture_sound is not None:
                    team.capture_sound.volume = self._sound_volume
            else:
                self._reset_team_capture(team)

    def _handle_score(self, enemy_team_being_captured: Team) -> None:
        """Handle scoring when a player successfully captures a flag."""
        if not enemy_team_being_captured.capturing_players:
            return

        capturing_player = enemy_team_being_captured.capturing_players[0]
        scoring_team = capturing_player.team

        # Prevent multiple simultaneous scores
        if bs.time() != self._last_score_time:
            self._last_score_time = bs.time()
            self.stats.player_scored(capturing_player, 50, big_message=True)
            self._score_sound.play()
            self._flash_base(enemy_team_being_captured)

            # Move all players on the scoring team back to their start
            # and add flashes of light so its noticeable.
            for player in scoring_team.players:
                if player.is_alive():
                    pos = player.node.position
                    light = bs.newnode(
                        'light',
                        attrs={
                            'position': pos,
                            'color': scoring_team.color,
                            'height_attenuated': False,
                            'radius': 0.4,
                        },
                    )
                    bs.timer(0.5, light.delete)
                    bs.animate(light, 'intensity', {0: 0, 0.1: 1.0, 0.5: 0})

                    new_pos = self.map.get_start_position(scoring_team.id)
                    light = bs.newnode(
                        'light',
                        attrs={
                            'position': new_pos,
                            'color': scoring_team.color,
                            'radius': 0.4,
                            'height_attenuated': False,
                        },
                    )
                    bs.timer(0.5, light.delete)
                    bs.animate(light, 'intensity', {0: 0, 0.1: 1.0, 0.5: 0})
                    if player.actor:
                        random_num = random.uniform(0, 360)

                        # Slightly hacky workaround: normally,
                        # teleporting back to base with a sticky
                        # bomb stuck to you gives a crazy whiplash
                        # rubber-band effect. Running the teleport
                        # twice in a row seems to suppress that
                        # though. Would be better to fix this at a
                        # lower level, but this works for now.
                        self._teleport(player, new_pos, random_num)
                        bs.timer(
                            0.01,
                            bs.CallPartial(
                                self._teleport, player, new_pos, random_num
                            ),
                        )

            # Have teammates celebrate.
            for player in scoring_team.players:
                if player.actor:
                    player.actor.handlemessage(bs.CelebrateMessage(2.0))

            scoring_team.score += 1
            self._update_scoreboard()

            # Reset capture state for this team only
            self._reset_team_capture(enemy_team_being_captured)

            if scoring_team.score >= self._score_to_win:
                self.end_game()

    def _teleport(
        self, client: Player, pos: Sequence[float], num: float
    ) -> None:
        if client.actor:
            client.actor.handlemessage(bs.StandMessage(pos, num))

    @override
    def end_game(self) -> None:
        results = bs.GameResults()
        for team in self.teams:
            results.set_team_score(team, team.score)
        self.end(results=results)

    def _update_scoreboard(self) -> None:
        for team in self.teams:
            self._scoreboard.set_team_value(
                team, team.score, self._score_to_win
            )
