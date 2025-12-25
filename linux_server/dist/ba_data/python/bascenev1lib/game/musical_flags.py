# Made by MattZ45986 on GitHub
# Ported by your friend: Freaku
# Modified for Caramel servers by SoK


# Bug Fixes & Improvements as well...

# Join BCS:
# https://discord.gg/ucyaesh


from __future__ import annotations
from typing import TYPE_CHECKING
import _babase
import random
import math
import bascenev1 as bs
from bascenev1lib.actor.spaz import CurseExplodeMessage
from bascenev1lib.actor.zoomtext import ZoomText
from bascenev1lib.actor.flag import Flag, FlagPickedUpMessage
from bascenev1lib.actor.playerspaz import PlayerSpaz
if TYPE_CHECKING:
    from typing import Any, Type, List, Dict, Tuple, Union, Sequence, Optional


class Player(bs.Player['Team']):
    def __init__(self) -> None:
        self.done: bool = False
        self.survived: bool = True


class Team(bs.Team[Player]):
    def __init__(self) -> None:
        self.score = 0


# ba_meta require api 9
# ba_meta export bascenev1.GameActivity
class MFGame(bs.TeamGameActivity[Player, Team]):
    name = 'Musical Flags'
    description = "Don't be the one stuck without a flag!"

    @classmethod
    def get_available_settings(
            cls, sessiontype: Type[bs.Session]) -> List[babase.Setting]:
        settings = [
            bs.IntSetting(
                'Max Round Time',
                min_value=15,
                default=25,
                increment=5,
            ),
            bs.BoolSetting('Epic Mode', default=False),
            bs.BoolSetting('Enable Running', default=True),
            bs.BoolSetting('Enable Punching', default=False),
            bs.BoolSetting('Enable Bottom Credit', True)
        ]
        return settings

    @classmethod
    def supports_session_type(cls, sessiontype: Type[bs.Session]) -> bool:
        return (issubclass(sessiontype, bs.DualTeamSession)
                or issubclass(sessiontype, bs.FreeForAllSession))

    @classmethod
    def get_supported_maps(cls, sessiontype: Type[bs.Session]) -> List[str]:
        return ['Doom Shroom']

    def __init__(self, settings: dict):
        super().__init__(settings)
        self.nodes = []
        self.texts = []
        self._dingsound = bs.getsound('dingSmall')
        self._epic_mode = bool(settings['Epic Mode'])
        self.credit_text = bool(settings['Enable Bottom Credit'])
        self.is_punch = bool(settings['Enable Punching'])
        self.is_run = bool(settings['Enable Running'])

        self._textRound = bs.newnode('text',
                                     attrs={'text': '',
                                            'position': (0, -38),
                                            'scale': 1,
                                            'shadow': 1.0,
                                            'flatness': 1.0,
                                            'color': (1.0, 0.0, 1.0),
                                            'opacity': 1,
                                            'v_attach': 'top',
                                            'h_attach': 'center',
                                            'h_align': 'center',
                                            'v_align': 'center'})
        self.round_time = int(settings['Max Round Time'])
        self.reset_round_time = int(settings['Max Round Time'])
        self.should_die_occur = True
        self.round_time_textnode = bs.newnode('text',
                                              attrs={
                                                  'text': "", 'flatness': 1.0, 'h_align': 'center', 'h_attach': 'center', 'v_attach': 'top', 'v_align': 'center', 'position': (0, -15), 'scale': 0.9, 'color': (1, 0.7, 0.9)})

        self.slow_motion = self._epic_mode
        # A cool music, matching our gamemode theme
        self.default_music = bs.MusicType.FLAG_CATCHER

    def get_instance_description(self) -> Union[str, Sequence]:
        return 'Grab a flag for yourself'

    def get_instance_description_short(self) -> Union[str, Sequence]:
        return 'Grab a flag for yourself'

    def on_player_join(self, player: Player) -> None:
        if self.has_begun():
            bs.broadcastmessage(
                bs.Lstr(resource='playerDelayedJoinText',
                        subs=[('${PLAYER}', player.getname(full=True))]),
                color=(0, 1, 0), transient=True)
            player.survived = False
            return
        self.spawn_player(player)

    def on_player_leave(self, player: Player) -> None:
        super().on_player_leave(player)
        # A departing player may trigger game-over.
        bs.timer(0, self.checkEnd)

    def on_begin(self) -> None:
        super().on_begin()
        self.roundNum = 0
        self.numPickedUp = 0
        self.nodes = []
        self.texts = []
        self.flags = []
        self.spawned = []
        if self.credit_text:
            t = bs.newnode('text',
                           attrs={'text': "Ported by Freaku\nMade by MattZ45986",  # Disable 'Enable Bottom Credits' when making playlist, No need to edit this lovely...
                                  'scale': 0.7,
                                  'position': (0, 0),
                                  'shadow': 0.5,
                                  'flatness': 1.2,
                                  'color': (1, 1, 1),
                                  'h_align': 'center',
                                  'v_attach': 'bottom'})
        self.makeRound()
        self._textRound.text = 'Round ' + str(self.roundNum)
        bs.timer(3, self.checkEnd)
        self.keepcalling = bs.timer(1, self._timeround, True)

    def _timeround(self):
        if self.round_time == 0 and self.should_die_occur:
            self.should_die_occur = False
            self.round_time_textnode.opacity = 0
            bs.broadcastmessage('Proceeding Round...')
            for player in self.spawned:
                if not player.done:
                    try:
                        player.survived = False
                        if player.actor and player.actor.node:
                            xforce = 40
                            yforce = 2
                            for x in range(5):
                                v = player.actor.node.velocity
                                player.actor.node.handlemessage('impulse', player.actor.node.position[0], player.actor.node.position[1], player.actor.node.position[2],
                                                                0, 25, 0,
                                                                yforce, 0.05, 0, 0,
                                                                0, 20 * 600, 0)
                                player.actor.node.handlemessage('impulse', player.actor.node.position[0], player.actor.node.position[1], player.actor.node.position[2],
                                                                0, 25, 0,
                                                                xforce, 0.05, 0, 0,
                                                                v[0] * 15 * 2, 0, v[2] * 15 * 2)
                            player.actor.handlemessage(CurseExplodeMessage())
                    except:
                        pass
            bs.timer(3.5, self.killRound)
            bs.timer(3.55, self.makeRound)
            self.round_time_textnode.opacity = 0
            self.round_time = self.reset_round_time
        else:
            self.round_time_textnode.text = "Time: " + str(self.round_time)
            self.round_time -= 1

    def makeRound(self):
        for player in self.players:
            if player.survived:
                player.team.score += 1
        self.roundNum += 1
        self._textRound.text = 'Round ' + str(self.roundNum)
        self.flags = []
        self.spawned = []
        self.should_die_occur = True
        self.round_time = self.reset_round_time
        self.round_time_textnode.opacity = 1
        angle = random.randint(0, 359)
        c = 0
        for player in self.players:
            if player.survived:
                c += 1
        spacing = 10
        for player in self.players:
            player.done = False
            if player.survived:
                if not player.is_alive():
                    self.spawn_player(player, (.5, 5, -4))
                self.spawned.append(player)
        try:
            spacing = 360 // (c)
        except:
            self.checkEnd()
        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (0, 0, 0),
                  (0.5, 0.8, 0), (0, 0.8, 0.5), (0.8, 0.25, 0.7), (0, 0.27, 0.55), (2, 2, 0.6), (0.4, 3, 0.85)]

        # Add support for more than 13 players
        if c > 12:
            for i in range(c-12):
                colors.append((random.uniform(0.1, 1), random.uniform(
                    0.1, 1), random.uniform(0.1, 1)))

        # Smart Mathematics:
        # All Flags spawn same distance from the players
        for i in range(c-1):
            angle += spacing
            angle %= 360
            x = 6 * math.sin(math.degrees(angle))
            z = 6 * math.cos(math.degrees(angle))
            flag = Flag(position=(x+.5, 3, z-4), color=colors[i]).autoretain()
            self.flags.append(flag)

    def killRound(self):
        self.numPickedUp = 0
        for player in self.players:
            if player.is_alive():
                player.actor.handlemessage(bs.DieMessage())
        for flag in self.flags:
            flag.node.delete()
        for light in self.nodes:
            bs.animate(light, 'intensity', {0: 1, 0.5: 0})
            bs.timer(0.5, light.delete)
        self.nodes = []
        for text in self.texts:
            bs.animate(text, 'scale', {0: 0.01, 0.5: 0})
            bs.timer(0.5, text.delete)
        self.texts = []

    def spawn_player(self, player: Player, pos: tuple = (0, 0, 0)) -> bs.Actor:
        spaz = self.spawn_player_spaz(player)
        if pos == (0, 0, 0):
            pos = (-.5+random.random()*2, 3+random.random()*2, -5+random.random()*2)
        spaz.connect_controls_to_player(enable_punch=self.is_punch,
                                        enable_bomb=False, enable_run=self.is_run)
        spaz.handlemessage(bs.StandMessage(pos))
        return spaz

    def check_respawn(self, player):
        if not player.done and player.survived:
            self.respawn_player(player, 2.5)

    def impulse_player(self, player):
        if player.actor and player.actor.node:
            xforce = 0
            yforce = 500
            for x in range(5):
                v = player.actor.node.velocity
                player.actor.node.handlemessage('impulse', player.actor.node.position[0], player.actor.node.position[1], player.actor.node.position[2],
                                                0, 25, 0,
                                                yforce, 0.05, 0, 0,
                                                0, 20 * 600, 0)
                player.actor.node.handlemessage('impulse', player.actor.node.position[0], player.actor.node.position[1], player.actor.node.position[2],
                                                0, 25, 0,
                                                xforce, 0.05, 0, 0,
                                                v[0] * 15 * 2, 0, v[2] * 15 * 2)

    def handlemessage(self, msg: Any) -> Any:

        if isinstance(msg, bs.PlayerDiedMessage):
            super().handlemessage(msg)
            player = msg.getplayer(Player)
            bs.timer(0.1, bs.CallPartial(self.check_respawn, player))
            bs.timer(0.5, self.checkEnd)
        elif isinstance(msg, FlagPickedUpMessage):
            self.numPickedUp += 1
            player = msg.node.getdelegate(PlayerSpaz, True).getplayer(Player, True)
            player.done = True
            l = bs.newnode('light',
                           owner=None,
                           attrs={'color': msg.node.color,
                                  'position': (msg.node.position_center),
                                  'radius': 0.1,
                                  'intensity': 0})
            bs.animate(l, 'intensity', {0: 0, 0.5: 1})
            self.nodes.append(l)
            t = bs.newnode('text',
                           owner=None,
                           attrs={'text': player.getname(),
                                  'in_world': True,
                                  'position': (msg.node.position[0], msg.node.position[1] + 1.0, msg.node.position[2]),
                                  'scale': 0,
                                  'shadow': 0.5,
                                  'flatness': 1.0,
                                  'color': bs.safecolor(player.team.color) + (1,),
                                  'h_align': 'center'})
            bs.animate(t, 'scale', {0: 0, 0.2: 0.01})
            self.texts.append(t)
            msg.flag.handlemessage(bs.DieMessage())
            msg.node.handlemessage(bs.DieMessage())
            msg.node.delete()
            if self.numPickedUp == len(self.flags):
                self.round_time_textnode.opacity = 0
                self.round_time = self.reset_round_time
                for player in self.spawned:
                    if not player.done:
                        try:
                            player.survived = False
                            ZoomText(
                                "No flag, " + player.getname() + "?", 
                                position=(0, 0), 
                                color=player.team.color, 
                                shiftposition=(0, -200), 
                                shiftdelay=0.1, 
                                flash=True, 
                                trail=True, 
                                scale=0.5,
                                lifespan=3, 
                                jitter=1.0).autoretain()

                            player.actor.node.handlemessage('knockout', 1000.0)
                            bs.timer(1.5, bs.CallPartial(self.impulse_player, player))
                            bs.timer(2.3, bs.CallStrict(player.actor.curse_explode))

                        except:
                            pass
                bs.timer(3.5, self.killRound)
                bs.timer(3.55, self.makeRound)
        else:
            return super().handlemessage(msg)
        return None

    def checkEnd(self):
        i = 0
        for player in self.players:
            if player.survived:
                i += 1
        if i <= 1:
            for player in self.players:
                if player.survived:
                    player.team.score += 10
            bs.timer(2.5, self.end_game)

    def end_game(self) -> None:
        results = bs.GameResults()
        for team in self.teams:
            results.set_team_score(team, team.score)
        self.end(results=results)
