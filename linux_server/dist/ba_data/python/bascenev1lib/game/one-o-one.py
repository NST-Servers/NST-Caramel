# Released under the MIT License. See LICENSE for details.
#
"""
One-o-One V3
----------------
A gamemode where players are put in a queue to fight 1v1.
First player to get a set number of kills wins.
----------------
Made by SoK
Requested by Neo
"""

# ba_meta require api 9

from __future__ import annotations

import random
import weakref
from typing import TYPE_CHECKING, override

import bascenev1 as bs
import babase

from bascenev1lib.actor.playerspaz import PlayerSpaz
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.actor.popuptext import PopupText

if TYPE_CHECKING:
    from typing import Any, Sequence


STALEMATE_TIME = 10
DEFAULT_WIN_POINTS = 15


class DuelPlayerSpaz(PlayerSpaz):
    """Custom player spaz for Duel mode."""

    def __init__(self, *args: Any, **kwargs: Any):
        position = kwargs.pop('position', None)
        angle = kwargs.pop('angle', None)

        # Set stuff accordingly
        player = kwargs.get('player')
        if player:
            kwargs.setdefault('character', player.character)
            kwargs.setdefault('color', player.color)
            kwargs.setdefault('highlight', player.highlight)

        super().__init__(*args, **kwargs)

        if player:
            self.connect_controls_to_player()
            self.node.name = player.getname()
            display_color = babase.safecolor(player.color, target_intensity=1)
            self.node.name_color = display_color

        if position is not None:
            self.handlemessage(bs.StandMessage(position, angle if angle is not None else 0))

        self._duel_game = weakref.ref(self.activity)
        self._invincibility_timer: bs.Timer | None = None

        # Extended I-Frames
        activity = self._duel_game()
        if activity and activity.extended_i_frames:
            # Vanilla invincibility is usually handled by the node itself
            # or the factory. We can force it here.
            self.node.invincible = True
            self._invincibility_timer = bs.Timer(
                1.01, bs.WeakCallPartial(self._maintain_invincibility), repeat=True
            )
            # Extend it. Vanilla is around 1s. We add another 1s.
            bs.timer(3.0, bs.WeakCallPartial(self._end_invincibility))

    def _maintain_invincibility(self) -> None:
        if self.node:
            self.node.invincible = True

    def _end_invincibility(self) -> None:
        self._invincibility_timer = None
        if self.node:
            self.node.invincible = False

    def spawn_scorch(self, pos: Sequence[float], mag: float, small: bool) -> None:
        scorch_size = (min(mag, 200) * 0.015) * (0.085 if small else 0.25)
        color = (1, 0, 0) if not small else (0.29, 0, 0)
        scorch = bs.newnode(
            'scorch',
            attrs={
                'position': pos,
                'size': scorch_size,
                'color': color,
                'big': not small,
            },
        )
        starting_presence = 2 if small else 1
        bs.animate(scorch, 'presence',{0: 0, 0.08: starting_presence, 2: starting_presence, 13: 0,})
        bs.timer(13, scorch.delete)

    @override
    def on_punched(self, damage: int) -> None:
        super().on_punched(damage)
        if self.hitpoints - damage <= 0 and damage >= 500:
            self.shatter(extreme=True)
            self._duel_game().on_spaz_shattered(self)

    @override
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.HitMessage):
            activity = self._duel_game()
            if activity:
                # Reset duel timer on combat
                if msg._source_player and msg._source_player != self.getplayer(bs.Player, False):
                    activity.on_duel_action()

            # Blood effect (Red Scorches)
            if self.node.invincible:
                return None
            if activity and activity.blood_enabled and msg.magnitude > 0:
                self.spawn_scorch(msg.pos, msg.magnitude, small=False)
                bs.timer(0.1, bs.WeakCallPartial(self.spawn_scorch, msg.pos, msg.magnitude, small=True))

            return super().handlemessage(msg)

        if isinstance(msg, bs.DieMessage):
            super().handlemessage(msg)
            # Remove Ragdolls
            activity = self._duel_game()
            if activity and activity.remove_ragdolls:
                # Delete the node shortly after death
                if self.node:
                    # Play sound
                    activity._pop.play(position=self.node.position, volume=1)

                    # Emit sparks
                    bs.emitfx(
                        position=self.node.position,
                        velocity=self.node.velocity,
                        count=5,
                        scale=0.8,
                        spread=0.8,
                        chunk_type='spark',
                    )
                    bs.timer(0.05, self.node.delete)
            return None

        return super().handlemessage(msg)


class Icon(bs.Actor):
    """Creates in in-game icon on screen."""

    def __init__(
        self,
        player: Player,
        position: tuple[float, float],
        scale: float,
        *,
        show_lives: bool = True,
        show_death: bool = True,
        name_scale: float = 1.0,
        name_maxwidth: float = 115.0,
        flatness: float = 1.0,
        shadow: float = 1.0,
        number: int | None = None,
    ):
        super().__init__()

        self._player = weakref.ref(player)
        self._show_lives = show_lives
        self._show_death = show_death
        self._name_scale = name_scale
        self._outline_tex = bs.gettexture('characterIconMask')

        icon = player.get_icon()
        self.node = bs.newnode(
            'image',
            delegate=self,
            attrs={
                'texture': icon['texture'],
                'tint_texture': icon['tint_texture'],
                'tint_color': icon['tint_color'],
                'vr_depth': 400,
                'tint2_color': icon['tint2_color'],
                'mask_texture': self._outline_tex,
                'opacity': 1.0,
                'absolute_scale': True,
                'attach': 'bottomCenter',
            },
        )
        self._name_text = bs.newnode(
            'text',
            owner=self.node,
            attrs={
                'text': bs.Lstr(value=player.getname()),
                'color': bs.safecolor(player.team.color),
                'h_align': 'center',
                'v_align': 'center',
                'vr_depth': 410,
                'maxwidth': name_maxwidth,
                'shadow': shadow,
                'flatness': flatness,
                'h_attach': 'center',
                'v_attach': 'bottom',
            },
        )
        self._number_text = bs.newnode(
            'text',
            owner=self.node,
            attrs={
                'text': str(number) if number is not None else '',
                'color': (1, 1, 1),
                'h_align': 'center',
                'v_align': 'center',
                'vr_depth': 410,
                'shadow': 1.0,
                'flatness': 1.0,
                'h_attach': 'center',
                'v_attach': 'bottom',
            },
        )
        self.set_position_and_scale(position, scale)

    def set_position_and_scale(
        self, position: tuple[float, float], scale: float
    ) -> None:
        """(Re)position the icon."""
        assert self.node
        self.node.position = position
        self.node.scale = [60.0 * scale]
        self._name_text.position = (position[0], position[1] + scale * 52.0)
        self._name_text.scale = 1.0 * scale * self._name_scale
        self._number_text.position = (position[0], position[1] - scale * 25.0)
        self._number_text.scale = 0.8 * scale

    def update_for_player(
        self,
        position: tuple[float, float],
        scale: float,
        name_maxwidth: float = 115.0,
        name_scale: float = 1.0,
        flatness: float = 1.0,
        shadow: float = 1.0,
        number: int | None = None,
    ) -> None:
        """Update the icon's position and other attributes."""
        if not self.node:
            return

        self._name_scale = name_scale
        if number is not None:
            self._number_text.text = str(number)
        else:
            self._number_text.text = ''

        # Current state
        cur_pos = self.node.position
        cur_scale = self.node.scale[0]
        target_scale = 70.0 * scale
        t = 0.15

        def _lerp(a: float, b: float, t: float) -> float:
            return a + (b - a) * t

        # Animate position and scale
        bs.animate_array(self.node, 'position', 2, {
            0: cur_pos,
            t * 0.2: (_lerp(cur_pos[0], position[0], 0.05), _lerp(cur_pos[1], position[1], 0.05)),
            t * 0.8: (_lerp(cur_pos[0], position[0], 0.95), _lerp(cur_pos[1], position[1], 0.95)),
            t: position
        })
        bs.animate_array(self.node, 'scale', 1, {
            0: (cur_scale,),
            t * 0.2: (_lerp(cur_scale, target_scale, 0.05),),
            t * 0.8: (_lerp(cur_scale, target_scale, 0.95),),
            t: (target_scale,)
        })

        # Update text
        self._name_text.maxwidth = name_maxwidth
        self._name_text.shadow = shadow
        self._name_text.flatness = flatness

        # Animate text position and scale
        cur_text_pos = self._name_text.position
        cur_text_scale = self._name_text.scale
        target_text_pos = (position[0], position[1] + scale * 52.0)
        target_text_scale = 1.0 * scale * name_scale

        bs.animate_array(self._name_text, 'position', 2, {
            0: cur_text_pos,
            t * 0.2: (_lerp(cur_text_pos[0], target_text_pos[0], 0.05), _lerp(cur_text_pos[1], target_text_pos[1], 0.05)),
            t * 0.8: (_lerp(cur_text_pos[0], target_text_pos[0], 0.95), _lerp(cur_text_pos[1], target_text_pos[1], 0.95)),
            t: target_text_pos
        })
        bs.animate(self._name_text, 'scale', {
            0: cur_text_scale,
            t * 0.2: _lerp(cur_text_scale, target_text_scale, 0.05),
            t * 0.8: _lerp(cur_text_scale, target_text_scale, 0.95),
            t: target_text_scale
        })

        # Animate number text
        cur_num_pos = self._number_text.position
        cur_num_scale = self._number_text.scale
        target_num_pos = (position[0], position[1] - scale * 25.0)
        target_num_scale = 0.8 * scale

        bs.animate_array(self._number_text, 'position', 2, {
            0: cur_num_pos,
            t * 0.2: (_lerp(cur_num_pos[0], target_num_pos[0], 0.05), _lerp(cur_num_pos[1], target_num_pos[1], 0.05)),
            t * 0.8: (_lerp(cur_num_pos[0], target_num_pos[0], 0.95), _lerp(cur_num_pos[1], target_num_pos[1], 0.95)),
            t: target_num_pos
        })
        bs.animate(self._number_text, 'scale', {
            0: cur_num_scale,
            t * 0.2: _lerp(cur_num_scale, target_num_scale, 0.05),
            t * 0.8: _lerp(cur_num_scale, target_num_scale, 0.95),
            t: target_num_scale
        })

    def handle_player_spawned(self) -> None:
        """Our player spawned; hooray!"""
        if not self.node:
            return
        self.node.opacity = 1.0

    def handle_player_died(self) -> None:
        """Well poo; our player died."""
        if not self.node:
            return

    @override
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            self.node.delete()
            return None
        return super().handlemessage(msg)


class Player(bs.Player['Team']):
    """Our player type for this game."""

    def __init__(self) -> None:
        self.streak = 0
        self.icons: list[Icon] = []
        self.stalemate_light: bs.Node | None = None


class Team(bs.Team[Player]):
    """Our team type for this game."""

    def __init__(self) -> None:
        self.score = 0


# ba_meta export bascenev1.GameActivity
class OneoOneGame(bs.TeamGameActivity[Player, Team]):
    """FFA gamemode where players queue to fight 1v1."""

    name = 'One-o-One'
    description = 'Defeat enemies in 1v1 combat.'
    announce_player_deaths = True
    allow_mid_activity_joins = True

    @override
    @classmethod
    def get_available_settings(
        cls, sessiontype: type[bs.Session]
    ) -> list[bs.Setting]:
        settings = [
            bs.IntSetting(
                'Kills to Win Per Player',
                min_value=5,
                default=DEFAULT_WIN_POINTS,
                increment=1,
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
            bs.BoolSetting('Toggleable Powerups', default=False),
            bs.BoolSetting('Default Shields', default=False),
            bs.BoolSetting('Default Boxing Gloves', default=False),
            bs.BoolSetting('Default Impact Bombs', default=False),
            bs.BoolSetting('Epic Mode', default=False),
            bs.BoolSetting('Allow Negative Scores', default=False),
            bs.BoolSetting('Kills Partially Heal', default=True),
            bs.BoolSetting('Killstreaks', default=True),
            bs.BoolSetting('Blood', default=False),
            bs.BoolSetting('Remove Ragdolls', default=False),
            bs.BoolSetting('Extended I-Frames', default=True),
        ]
        return settings

    @override
    @classmethod
    def supports_session_type(cls, sessiontype: type[bs.Session]) -> bool:
        return issubclass(sessiontype, bs.FreeForAllSession)

    @override
    @classmethod
    def get_supported_maps(cls, sessiontype: type[bs.Session]) -> list[str]:
        assert bs.app.classic is not None
        return bs.app.classic.getmaps('melee')

    def __init__(self, settings: dict):
        super().__init__(settings)
        self._scoreboard = Scoreboard()
        self._kills_to_win = int(settings['Kills to Win Per Player'])
        self._time_limit = float(settings['Time Limit'])
        self._powerups_enabled = bool(settings['Toggleable Powerups'])
        self._start_shield = bool(settings['Default Shields'])
        self._start_gloves = bool(settings['Default Boxing Gloves'])
        self._start_impact_bombs = bool(settings['Default Impact Bombs'])
        self._epic_mode = bool(settings['Epic Mode'])
        self._allow_negative_scores = bool(settings['Allow Negative Scores'])
        self._kills_heal = bool(settings['Kills Partially Heal'])
        self._killstreaks = bool(settings['Killstreaks'])
        self.blood_enabled = bool(settings['Blood'])
        self.remove_ragdolls = bool(settings['Remove Ragdolls'])
        self.extended_i_frames = bool(settings['Extended I-Frames'])

        self._last_combat_action_time = 0.0
        self._queue: list[Player] = []
        self._current_duel: list[Player] = []
        self._dingsound = bs.getsound('dingSmall')
        self._drum_roll_short = bs.getsound('drumRollShort')
        self._orchestra_hit_1 = bs.getsound('orchestraHit')
        self._orchestra_hit_2 = bs.getsound('orchestraHit2')
        self._orchestra_hit_3 = bs.getsound('orchestraHit3')
        self._orchestra_hit_4 = bs.getsound('orchestraHit4')
        self._orchestra_hit_big_1 = bs.getsound('orchestraHitBig1')
        self._orchestra_hit_big_2 = bs.getsound('orchestraHitBig2')
        self._announcer_2 = bs.getsound('announceTwo')
        self._announcer_3 = bs.getsound('announceThree')
        self._announcer_4 = bs.getsound('announceFour')
        self._announcer_5 = bs.getsound('announceFive')
        self._announcer_6 = bs.getsound('announceSix')
        self._announcer_7 = bs.getsound('announceSeven')
        self._announcer_8 = bs.getsound('announceEight')
        self._announcer_9 = bs.getsound('announceNine')
        self._announcer_10 = bs.getsound('announceTen')
        self._pop = bs.getsound('pop01')
        self._cork_pop_2 = bs.getsound('corkPop2')
        self._shatter_score = bs.getsound('score')
        self._blast = bs.getsound('explosion01')
        self._oh_yeah = bs.getsound('yeah')
        self._heal_sound = bs.getsound('healthPowerup')
        self._cash_register_sound = bs.getsound('cashRegister2')
        self._vs_text: bs.Actor | None = None
        self._round_end_timer: bs.Timer | None = None
        self._current_music: bs.MusicType | None = None

        # Base class overrides.
        self.slow_motion = self._epic_mode
        self.default_music = bs.MusicType.GRAND_ROMP

    @override
    def get_instance_description(self) -> str | Sequence:
        return 'Defeat ${ARG1} enemies.', self._kills_to_win

    @override
    def get_instance_description_short(self) -> str | Sequence:
        return 'kill ${ARG1} enemies', self._kills_to_win

    @override
    def on_begin(self) -> None:
        super().on_begin()
        self.setup_standard_time_limit(self._time_limit)
        if self._powerups_enabled:
            self.setup_standard_powerup_drops()

        # Initialize queue with all players
        self._queue = list(self.players)
        random.shuffle(self._queue)

        self._update_scoreboard()
        self._update_icons()
        self._start_next_duel()
        bs.timer(1.0, self._update, repeat=True)
        self._last_combat_action_time = bs.time()

    def on_duel_action(self) -> None:
        """Called when combat occurs in a duel."""
        self._last_combat_action_time = bs.time()
        for player in self._current_duel:
            if player.stalemate_light:
                player.stalemate_light.delete()
                player.stalemate_light = None

    def _start_next_duel(self) -> None:
        # If we don't have enough players in the arena, spawn from queue
        while len(self._current_duel) < 2 and self._queue:
            player = self._queue.pop(0)
            self._current_duel.append(player)
            self.spawn_player(player)

        self._update_icons()
        self._last_combat_action_time = bs.time()

    def _update_dynamic_music(self) -> None:
        """Updates game music based on the current highest streak."""
        if not self._current_duel:
            return

        highest_streak = max(player.streak for player in self._current_duel)

        if highest_streak >= 10:
            music = bs.MusicType.EPIC
        elif highest_streak >= 8:
            music = bs.MusicType.SCARY
        elif highest_streak >= 6:
            music = bs.MusicType.FLYING
        elif highest_streak >= 4:
            music = bs.MusicType.SURVIVAL
        elif highest_streak >= 2:
            music = bs.MusicType.FLAG_CATCHER
        else:
            music = self.default_music

        if music != self._current_music:
            self._current_music = music
            bs.setmusic(music, continuous=True)

    def _update(self) -> None:
        # If we have no players, start a timer to end
        # the game.
        if len(self.players) < 1:
            self._round_end_timer = bs.Timer(0.5, self.end_game)

        # Stalemate logic
        if len(self._current_duel) == 2:
            t = bs.time()
            if t - self._last_combat_action_time > STALEMATE_TIME:
                self._apply_stalemate_damage(t)
            else:
                self._clear_stalemate_lights()

    def _apply_stalemate_damage(self, current_time: float) -> None:
        # Ramp up damage
        damage = int((current_time - self._last_combat_action_time - STALEMATE_TIME) * 25.0)
        if damage > 0:
            for player in self._current_duel:
                if player.actor and player.actor.node:
                    player.actor.node.handlemessage('hurt_sound')
                    player.actor.handlemessage(
                        bs.HitMessage(
                            flat_damage=damage,
                            pos=player.actor.node.position,
                            force_direction=(0, 1, 0),
                            hit_type='impact',
                        )
                    )

                    # Create light
                    if player.stalemate_light is None:
                        player.stalemate_light = bs.newnode(
                            'light',
                            attrs={
                                'position': player.actor.node.position,
                                'color': (1, 0, 0),
                                'radius': 0.06,
                                'intensity': 1.0,
                                'volume_intensity_scale': 1.0,
                            },
                        )
                        player.actor.node.connectattr(
                            'position', player.stalemate_light, 'position'
                        )

                        # Popup
                        PopupText(
                            'Fight!',
                            color=(1, 0, 0),
                            scale=2.0,
                            position=player.actor.node.position,
                        ).autoretain()

    def _clear_stalemate_lights(self) -> None:
        for player in self._current_duel:
            if player.stalemate_light:
                player.stalemate_light.delete()
                player.stalemate_light = None

    def _get_spawn_point(self, player: Player) -> bs.Vec3 | None:
        # Use spawn1 and spawn2 from map.
        if not self.map.spawn_points:
            return None

        s1 = self.map.spawn_points[0]
        s2 = self.map.spawn_points[1] if len(self.map.spawn_points) > 1 else s1
        p1 = bs.Vec3(s1[0], s1[1], s1[2])
        p2 = bs.Vec3(s2[0], s2[1], s2[2])

        # Check if there is an opponent alive in the arena.
        opponent: Player | None = None
        for p in self._current_duel:
            if p is not player and p.is_alive() and p.node:
                opponent = p
                break

        # If we have an opponent, spawn farthest from them.
        if opponent:
            opp_pos = opponent.node.position
            dist1 = (bs.Vec3(opp_pos) - p1).length()
            dist2 = (bs.Vec3(opp_pos) - p2).length()
            return p1 if dist1 > dist2 else p2

        # If no opponent (new duel), spawn based on HUD icon side.
        # Index 0 is Left (spawn1), Index 1 is Right (spawn2).
        if player in self._current_duel:
            idx = self._current_duel.index(player)
            if idx == 0:
                return p1
            if idx == 1:
                return p2

        return p1

    def on_spaz_shattered(self, spaz: DuelPlayerSpaz) -> None:
        """Called when a DuelPlayerSpaz shatters."""

        # Show Fatality popup
        pos = (
            spaz.node.position[0],
            spaz.node.position[1] - 1,
            spaz.node.position[2],
        )
        PopupText(
            'FATALITY!',
            color=(1, 0, 0),
            scale=2.0,
            position=pos,
        ).autoretain()

        # Make a flash
        flash = bs.newnode(
            'flash',
            attrs={
                'position': spaz.node.position,
                'size': 1.15,
                'color': (1, 0, 0),
            },
        )

        bs.timer(0.4, flash.delete)

        # Sparks
        bs.emitfx(
            position=spaz.node.position,
            velocity=(0, 1, 0),
            count=15,
            scale=1.25,
            spread=1.25,
            chunk_type='spark',
        )

        # Light
        light = bs.newnode(
            'light',
            attrs={
                'position': spaz.node.position,
                'radius': 0.3,
                'color': (1, 0, 0),
                'volume_intensity_scale': 1.0,
            },
        )

        # Animation and deletion
        bs.animate(light, 'intensity', {0: 0.0, 0.15: 1, 0.22: 1.15, 0.55: 0})
        bs.animate(light, 'radius', {0: 0.0, 0.15: 0.3, 0.22: 0.4, 0.55: 0})
        bs.timer(0.5, light.delete)

        # Epic mode for epicness..?
        self._globalsnode.slow_motion = True
        bs.timer(0.5, self._set_slow_motion_false)

        # Play sounds
        self._shatter_score.play(position=spaz.node.position, volume=1.5)
        self._blast.play(position=spaz.node.position, volume=2.5)
        self._oh_yeah.play(position=spaz.node.position, volume=1.25)

    def _set_slow_motion_false(self) -> None:
        self.globalsnode.slow_motion = False

    @override
    def spawn_player(self, player: Player) -> bs.Actor:
        actor = self.spawn_player_spaz(player, self._get_spawn_point(player))

        # Apply start items
        if self._start_shield:
            actor.equip_shields()
        if self._start_gloves:
            actor.equip_boxing_gloves()
        if self._start_impact_bombs:
            actor.bomb_type = 'impact'

        # Update icons to show alive state
        for icon in player.icons:
            icon.handle_player_spawned()

        return actor

    @override
    def spawn_player_spaz(
        self,
        player: Player,
        position: Sequence[float] | None = None,
        angle: float | None = None,
    ) -> bs.Actor:
        if position is None:
            position = self.map.get_ffa_start_position(self.players)
        angle = angle if angle is not None else 0.0
        spaz = DuelPlayerSpaz(player=player, position=position, angle=angle)
        player.actor = spaz
        return spaz

    @override
    def handlemessage(self, msg: Any) -> Any:
        # pylint: disable=too-many-nested-blocks
        if isinstance(msg, bs.PlayerDiedMessage):
            super().handlemessage(msg)
            victim = msg.getplayer(Player)
            killer = msg.getkillerplayer(Player)

            # Reset victim streak
            victim.streak = 0
            if victim.stalemate_light:
                victim.stalemate_light.delete()
                victim.stalemate_light = None
            for icon in victim.icons:
                icon.handle_player_died()

            # Handle Killer
            if killer and killer is not victim:
                killer.team.score += 1
                killer.streak += 1

                streak = killer.streak
                heal_percent = 0.0
                streak_text = ''
                sounds = []

                if streak == 1:
                    streak_text = 'First Blood!'
                    heal_percent = 0.80
                    sounds = [(self._drum_roll_short, 0.5), (self._orchestra_hit_1, 1.0)]
                elif streak == 2:
                    streak_text = 'Killing Spree!'
                    heal_percent = 0.60
                    sounds = [(self._announcer_2, 1.0), (self._orchestra_hit_2, 1.0)]
                elif streak == 3:
                    streak_text = 'Rampage!'
                    heal_percent = 0.40
                    sounds = [(self._announcer_3, 1.0), (self._orchestra_hit_3, 1.0)]
                elif streak == 4:
                    streak_text = 'Dominating!'
                    heal_percent = 0.20
                    sounds = [(self._announcer_4, 1.0), (self._orchestra_hit_4, 1.0)]
                elif streak == 5:
                    streak_text = 'Unstoppable!'
                    heal_percent = 0.10
                    sounds = [(self._announcer_5, 1.0), (self._orchestra_hit_big_1, 1.0)]
                elif streak == 6:
                    streak_text = 'GODLIKE!'
                    heal_percent = 0.10
                    sounds = [(self._announcer_6, 1.0), (self._orchestra_hit_big_2, 2.0)]
                elif streak <= 10:
                    streak_text = 'GODLIKE!'
                    heal_percent = 0.10
                    announcers = {
                        7: self._announcer_7,
                        8: self._announcer_8,
                        9: self._announcer_9,
                        10: self._announcer_10,
                    }
                    if streak in announcers:
                        sounds.append((announcers[streak], 1.0))
                    sounds.append((self._orchestra_hit_big_2, 2))
                else:
                    streak_text = 'GODLIKE!'
                    heal_percent = 0.10
                    sounds = [(self._cork_pop_2, 1.0)]

                # Update music
                self._update_dynamic_music()

                for sound, vol in sounds:
                    sound.play(volume=vol)

                health_restored_percent = 0

                # Heal Killer
                if self._kills_heal and killer.actor:
                    heal_amount = int(killer.actor.hitpoints_max * heal_percent)
                    current_hp = killer.actor.hitpoints
                    max_hp = killer.actor.hitpoints_max
                    new_hp = min(max_hp, current_hp + heal_amount)

                    # Calculate actual percent healed
                    if new_hp > current_hp:
                        health_restored = new_hp - current_hp
                        health_restored_percent = (
                            health_restored / max_hp
                        ) * 100

                        # Do our visuals and sound only if the killer actually healed
                        # Sparks
                        if killer.actor and killer.actor.node:
                            bs.emitfx(
                                position=killer.actor.node.position,
                                velocity=(0, 1, 0),
                                count=8,
                                scale=1.0,
                                spread=0.8,
                                chunk_type='spark',
                            )

                        # Flash
                        if killer.actor and killer.actor.node:
                            flash = bs.newnode(
                                'flash',
                                attrs={
                                    'position': killer.actor.node.position,
                                    'size': 0.8,
                                    'color': (0, 1, 0),
                                },
                            )
                            bs.timer(0.075, flash.delete)

                            # Light
                            light = bs.newnode(
                                'light',
                                attrs={
                                    'position': killer.actor.node.position,
                                    'radius': 0.2,
                                    'color': (0, 1, 0),
                                    'volume_intensity_scale': 1.0,
                                },
                            )
                            # Connect to Spaz
                            killer.actor.node.connectattr('torso_position', light, 'position')

                            # Animation and deletion
                            bs.animate(light, 'intensity', {0: 0.8, 0.5: 0})
                            bs.timer(0.5, light.delete)

                        # Sounds
                        self._heal_sound.play(
                            position=killer.actor.node.position, volume=1.0
                        )
                        self._cash_register_sound.play(
                            position=killer.actor.node.position, volume=1.0
                        )

                    # Update health
                    killer.actor.hitpoints = new_hp
                    killer.actor._last_hit_time = None
                    killer.actor._num_times_hit = 0
                    killer.actor.node.hurt = 1.0 - (
                        float(new_hp) / float(max_hp)
                    )

                    # Popup
                    if self._killstreaks and killer.actor:
                        popup_text = streak_text
                        if health_restored_percent > 0:
                            popup_text += f'\n+{health_restored_percent:.0f}% HP'
                        PopupText(
                            popup_text,
                            color=killer.actor.node.name_color,
                            scale=1.5,
                            position=killer.actor.node.position,
                        ).autoretain()


            # Handle suicide.
            elif killer is None or killer is victim:
                # If a dueling player suicides, the other player gets the
                # point, provided they are still alive.
                # We also substract a point from our suicider

                if self._allow_negative_scores:
                    victim.team.score -= 1
                else:
                    victim.team.score = max(0, victim.team.score - 1)

            self._update_scoreboard()

            # Check Win Condition
            if any(team.score >= self._kills_to_win for team in self.teams):
                bs.timer(0.5, self.end_game)

            # Queue Logic
            # Victim leaves the arena and goes to back of queue
            if victim in self._current_duel:
                self._current_duel.remove(victim)
                self._queue.append(victim)

            # Delay before spawning next player to allow death animation/popup
            bs.timer(1.5, self._start_next_duel)

        else:
            return super().handlemessage(msg)
        return None

    def _update_scoreboard(self) -> None:
        for team in self.teams:
            self._scoreboard.set_team_value(
                team, team.score, self._kills_to_win
            )

    def _update_icons(self) -> None:
        # Create the VS text if it doesn't exist
        if not self._vs_text:
            self._vs_text = bs.NodeActor(
                bs.newnode(
                    'text',
                    attrs={
                        'position': (0, 95),
                        'h_attach': 'center',
                        'h_align': 'center',
                        'maxwidth': 200,
                        'shadow': 0.5,
                        'vr_depth': 390,
                        'scale': 0.7,
                        'v_attach': 'bottom',
                        'color': (0.8, 0.8, 0.3, 1.0),
                        'text': 'vs',
                    },
                )
            )

        # Map players to their target state
        player_states = {}

        # Duelists
        if len(self._current_duel) > 0:
            player_states[self._current_duel[0]] = {
                'position': (-90, 93),
                'scale': 0.8,
                'name_maxwidth': 100,
                'name_scale': 0.8,
                'flatness': 0.0,
                'shadow': 0.5,
            }
        if len(self._current_duel) > 1:
            player_states[self._current_duel[1]] = {
                'position': (90, 93),
                'scale': 0.8,
                'name_maxwidth': 100,
                'name_scale': 0.8,
                'flatness': 0.0,
                'shadow': 0.5,
            }

        # Queue
        if self._queue:
            queue_len = len(self._queue)
            spacing = 50.0
            max_width = 600.0
            if queue_len > 1:
                spacing = min(50.0, max_width / (queue_len - 1))
            x_start = -spacing * (queue_len - 1) * 0.5
            for i, player in enumerate(self._queue):
                scl = 0.65 if i == 0 else 0.55
                player_states[player] = {
                    'position': (x_start + i * spacing, 25),
                    'scale': scl,
                    'name_maxwidth': 100,
                    'name_scale': 0.6,
                    'flatness': 1.0,
                    'shadow': 0.0,
                    'number': i + 1,
                }

        # Apply states
        for player in self.players:
            if player in player_states:
                state = player_states[player]
                if not player.icons:
                    icon = Icon(
                        player,
                        position=state['position'],
                        scale=state['scale'],
                        name_maxwidth=state['name_maxwidth'],
                        name_scale=state['name_scale'],
                        flatness=state['flatness'],
                        shadow=state['shadow'],
                        show_lives=False,
                        number=state.get('number'),
                    )
                    player.icons.append(icon)
                else:
                    icon = player.icons[0]
                    icon.update_for_player(**state)
            else:
                # Player not in duel or queue
                for icon in player.icons:
                    icon.handlemessage(bs.DieMessage())
                player.icons = []

    @override
    def on_player_join(self, player: Player) -> None:
        # Add new player to queue
        if player not in self._queue and player not in self._current_duel:
            self._queue.append(player)

        if self.has_begun():
            # If we have a pending game-end timer (because we were alone),
            # kill it.
            self._round_end_timer = None
            self._start_next_duel()

        self._update_icons()
        self._update_scoreboard()

    @override
    def on_player_leave(self, player: Player) -> None:
        super().on_player_leave(player)
        if player.stalemate_light:
            player.stalemate_light.delete()
            player.stalemate_light = None
        if player in self._queue:
            self._queue.remove(player)
        if player in self._current_duel:
            self._current_duel.remove(player)
            # If a fighter leaves, we need to fill the spot immediately
            self._start_next_duel()

        # Clean up icons
        player.icons = []
        bs.timer(0, self._update_icons)

    @override
    def end_game(self) -> None:
        if self.has_ended():
            return
        results = bs.GameResults()
        for team in self.teams:
            results.set_team_score(team, team.score)
        self.end(results=results)